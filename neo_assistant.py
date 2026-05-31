#!/usr/bin/env python
import os
import sys
import argparse
from src.config import NeoConfig
from src.repo_scanner import scan_repository, format_context_for_llm
from src.llm_client import LLMClient
from src.session_manager import SessionManager
from src.executor import execute_script

def load_skill_file(skills_dir, skill_name):
    path = os.path.join(skills_dir, f"{skill_name}.md")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Skill file not found at: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def clean_script_content(raw_content):
    """Strips markdown codeblock fences if present to get raw script code."""
    content = raw_content.strip()
    lines = content.split('\n')
    if len(lines) >= 2 and lines[0].startswith('```') and lines[-1].startswith('```'):
        return '\n'.join(lines[1:-1]).strip()
    # Sometimes it has a leading ```bash or ```powershell without trailing backticks
    if lines[0].startswith('```'):
        return '\n'.join(lines[1:]).strip()
    return content

def main():
    parser = argparse.ArgumentParser(description="NeoAssistantCoding - Assistant de codage sécurisé")
    parser.add_argument("--mode", required=True, choices=["architect", "developer", "git"], 
                        help="Mode de l'assistant: architect (conception), developer (codage), git (versioning)")
    parser.add_argument("--repo", required=True, 
                        help="Chemin du dépôt cible (qui peut être vide)")
    parser.add_argument("--goal", help="Objectif de la session sous forme de texte")
    parser.add_argument("--goal-file", help="Chemin vers un fichier MD contenant l'objectif")
    parser.add_argument("--config", default="config.json", help="Chemin vers le fichier de configuration JSON")
    
    args = parser.parse_args()
    
    # 1. Load config
    try:
        config = NeoConfig(args.config)
        config.validate()
    except Exception as e:
        print(f"[-] Erreur de configuration: {e}")
        sys.exit(1)
        
    # 2. Get goal
    goal = ""
    if args.goal:
        goal = args.goal
    elif args.goal_file:
        if os.path.exists(args.goal_file):
            with open(args.goal_file, 'r', encoding='utf-8') as f:
                goal = f.read()
        else:
            print(f"[-] Fichier d'objectif introuvable: {args.goal_file}")
            sys.exit(1)
    else:
        # Prompt interactively
        print("[*] Aucun objectif spécifié. Veuillez saisir l'objectif ci-dessous:")
        goal = input("> ").strip()
        if not goal:
            print("[-] Objectif vide. Fin de session.")
            sys.exit(1)
            
    # 3. Load skills
    try:
        common_skill = load_skill_file(config.skills_dir, "neo_assistant_coding")
        mode_skill = load_skill_file(config.skills_dir, args.mode)
    except Exception as e:
        print(f"[-] Erreur lors du chargement des fichiers de compétences (skills): {e}")
        sys.exit(1)
        
    system_instruction = f"{common_skill}\n\n{mode_skill}"
    
    # 4. Scan Repository
    print(f"[*] Analyse du dépôt cible: {args.repo} ...")
    files_dict, tree_str = scan_repository(args.repo, config.max_file_size_kb)
    repo_context = format_context_for_llm(files_dict, tree_str)
    
    # 5. Initialize session
    print("[*] Initialisation de la session de travail...")
    session = SessionManager(config.sessions_dir, args.repo)
    session.save_context(repo_context)
    
    llm = LLMClient(config)
    
    # Interactive history
    history = []
    
    # --- PHASE 1: GENERATION DU PLAN ---
    print("\n" + "="*50)
    print(f"[*] PHASE 1: CONCEPTION DU PLAN (Mode: {args.mode.upper()})")
    print("="*50)
    
    prompt = (
        f"Voici le contexte actuel du dépôt cible :\n\n{repo_context}\n\n"
        f"L'objectif de cette session est :\n{goal}\n\n"
        f"Rédige un plan d'action détaillé au format Markdown pour atteindre cet objectif."
    )
    
    plan_path = ""
    while True:
        print("[*] Demande de génération/mise à jour du plan au LLM...")
        try:
            plan_response = llm.generate(system_instruction, history, prompt)
        except Exception as e:
            print(f"[-] Erreur API LLM: {e}")
            sys.exit(1)
            
        plan_path = session.save_plan(plan_response)
        
        # Windows clickable link format
        clickable_link = f"file:///{plan_path.replace('\\', '/')}"
        print(f"\n[+] Plan d'action mis à jour.")
        print(f"[+] LIEN DU PLAN: {clickable_link}")
        print("\nEntrez 'OK' pour valider le plan, 'exit' pour quitter, ou saisissez votre commentaire pour l'ajuster:")
        
        user_input = input("> ").strip()
        if user_input.lower() == 'exit':
            print("[*] Session fermée par l'utilisateur. Le plan actuel a été sauvegardé.")
            sys.exit(0)
        elif user_input.upper() == 'OK':
            print("[+] Plan approuvé par l'utilisateur !")
            # Add to history to keep LLM synced
            history.append({"role": "user", "text": prompt})
            history.append({"role": "model", "text": plan_response})
            break
        else:
            # Loop again with user feedback
            history.append({"role": "user", "text": prompt})
            history.append({"role": "model", "text": plan_response})
            prompt = f"L'utilisateur a demandé d'ajuster le plan d'action avec le commentaire suivant :\n{user_input}\n\nMets à jour le plan d'action en conséquence."

    # --- PHASE 2: GENERATION DU SCRIPT ---
    print("\n" + "="*50)
    print(f"[*] PHASE 2: GENERATION DU SCRIPT D'EXECUTION ({config.shell.upper()})")
    print("="*50)
    
    script_ext = "ps1" if config.shell in ["powershell", "ps"] else "sh"
    if config.shell == "cmd":
        script_ext = "bat"
        
    prompt = (
        f"Le plan d'action a été approuvé par l'utilisateur. "
        f"Rédige maintenant un script complet d'exécution au format '{config.shell}' pour réaliser les modifications prévues dans le plan. "
        f"Le script doit être directement exécutable sans intervention manuelle. "
        f"Règle cruciale : Retourne UNIQUEMENT le code brut du script, sans explications textuelles autour (ou encapsulé dans un bloc de code)."
    )
    
    script_path = ""
    while True:
        print("[*] Demande de génération/mise à jour du script au LLM...")
        try:
            script_response = llm.generate(system_instruction, history, prompt)
        except Exception as e:
            print(f"[-] Erreur API LLM: {e}")
            sys.exit(1)
            
        cleaned_script = clean_script_content(script_response)
        script_path = session.save_script(cleaned_script, script_ext)
        
        clickable_link = f"file:///{script_path.replace('\\', '/')}"
        print(f"\n[+] Script d'exécution mis à jour.")
        print(f"[+] LIEN DU SCRIPT: {clickable_link}")
        print("\nEntrez 'OK' pour valider et exécuter le script, 'exit' pour quitter, ou saisissez votre commentaire pour l'ajuster:")
        
        user_input = input("> ").strip()
        if user_input.lower() == 'exit':
            print("[*] Session fermée par l'utilisateur. Le script actuel a été sauvegardé.")
            sys.exit(0)
        elif user_input.upper() == 'OK':
            print("[+] Script approuvé par l'utilisateur !")
            history.append({"role": "user", "text": prompt})
            history.append({"role": "model", "text": script_response})
            break
        else:
            # Loop again with user feedback
            history.append({"role": "user", "text": prompt})
            history.append({"role": "model", "text": script_response})
            prompt = f"L'utilisateur a demandé d'ajuster le script avec le commentaire suivant :\n{user_input}\n\nMets à jour le script en conséquence."

    # --- PHASE 3: BACKUP ET EXECUTION ---
    print("\n" + "="*50)
    print("[*] PHASE 3: SAUVEGARDE ET EXECUTION")
    print("="*50)
    
    print("[*] Création d'une sauvegarde de l'état actuel du dépôt cible...")
    session.backup_repository()
    print(f"[+] Sauvegarde effectuée dans: {session.backup_path}")
    
    print(f"[*] Exécution du script dans le dépôt cible ({args.repo})...")
    success, log_output = execute_script(script_path, args.repo, config.shell)
    
    if success:
        print("[+] Le script s'est exécuté avec succès (Code retour 0) !")
    else:
        print("[-] L'exécution du script a échoué.")
        
    print("\n--- RAPPORTS D'EXECUTION ---")
    print(log_output)
    print("----------------------------\n")
    
    # Prompt for rollback
    print("Voulez-vous annuler les modifications et restaurer l'état initial ? (oui/non - défaut: non)")
    rollback_choice = input("> ").strip().lower()
    if rollback_choice in ['o', 'oui', 'y', 'yes']:
        print("[*] Restauration du dépôt à partir de la sauvegarde...")
        if session.rollback_repository():
            print("[+] Restauration complétée avec succès.")
        else:
            print("[-] Échec de la restauration.")
    else:
        print("[+] Modifications conservées.")

    # --- PHASE 4: ARCHIVAGE ---
    print("\n" + "="*50)
    print("[*] PHASE 4: ARCHIVAGE DE LA SESSION")
    print("="*50)
    
    print("[*] Demande de génération du résumé au LLM...")
    summary_prompt = (
        f"L'exécution est maintenant terminée. Rédige un court résumé au format Markdown "
        f"résumant ce qui a été réalisé et le statut final par rapport à l'objectif : '{goal}'."
    )
    try:
        summary_response = llm.generate(system_instruction, history, summary_prompt)
    except Exception as e:
        print(f"[-] Avertissement: Échec de génération du résumé via LLM ({e}). Utilisation d'un résumé générique.")
        summary_response = f"# Résumé de session\n\nObjectif: {goal}\nStatut: Terminé"
        
    summary_path = session.save_summary(summary_response)
    print(f"[+] Résumé sauvegardé dans: {summary_path}")
    
    print("[*] Création de l'archive ZIP...")
    zip_path = session.archive_session()
    if zip_path:
        clickable_zip = f"file:///{zip_path.replace('\\', '/')}"
        print(f"[+] SESSION ARCHIVÉE AVEC SUCCÈS !")
        print(f"[+] ARCHIVE ZIP: {clickable_zip}")
    else:
        print("[-] Échec de la création de l'archive ZIP.")
        
    print("\n[*] Fin de NeoAssistantCoding. Merci !")

if __name__ == "__main__":
    main()
