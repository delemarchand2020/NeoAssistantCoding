# NeoAssistantCoding

**NeoAssistantCoding** est un assistant de codage local en Python, conçu sans framework lourd et orienté vers la sécurité grâce à un principe d'approbation humaine systématique pour chaque action critique (Humain dans la boucle).

## Architecture

Le projet est structuré comme suit :
- `neo_assistant.py` : Point d'entrée de la ligne de commande (CLI) et boucle d'orchestration.
- `config.json` : Fichier de configuration JSON pour spécifier le modèle LLM, la clé API, le shell par défaut et les limites.
- `skills/` : Dossier contenant les fichiers système Markdown (`neo_assistant_coding.md`, `architect.md`, `developer.md`, `git.md`).
- `src/` : Modules Python internes :
  - `config.py` : Chargement et validation de la configuration.
  - `repo_scanner.py` : Scan récursif du dépôt cible respectant les exclusions standard et `.gitignore`.
  - `llm_client.py` : Client API Gemini/OpenAI implémenté via `urllib.request` (aucune dépendance tierce).
  - `session_manager.py` : Gestion des sessions, sauvegardes automatiques et archivage ZIP.
  - `executor.py` : Exécution sécurisée des scripts et rollback.

---

## Configuration

1. Ouvrez [config.json](file:///c:/Users/delem/ProjetsAntigravity/NeoAssistantCoding/config.json).
2. Configurez vos paramètres :
   - `llm.provider` : `"gemini"` ou `"openai"`
   - `llm.api_key` : Votre clé API (ou `"ENV"` pour charger automatiquement depuis les variables d'environnement `GEMINI_API_KEY` ou `OPENAI_API_KEY`).
   - `llm.model` : Nom du modèle (ex. `"gemini-2.5-flash"` ou `"gpt-4o"`).
   - `shell` : Le shell utilisé pour exécuter les scripts (`"powershell"` ou `"bash"`).

---

## Utilisation

Lancez l'assistant depuis votre console (PowerShell ou Bash) en spécifiant le mode et le dépôt cible :

```bash
python neo_assistant.py --mode [architect|developer|git] --repo [chemin/du/depot]
```

### Options de Ligne de Commande

- `--mode` (Requis) : Choix du mode d'opération :
  - `architect` : Aide à la conception architecturale de projets.
  - `developer` : Écriture et modification de code source.
  - `git` : Gestion du dépôt Git (branches, commits, etc.).
- `--repo` (Requis) : Le chemin vers le dépôt sur lequel l'assistant doit travailler.
- `--goal` (Optionnel) : L'objectif de la session (ex: `"Créer une classe d'authentification"`). S'il n'est pas fourni, l'assistant vous le demandera interactivement.
- `--goal-file` (Optionnel) : Le chemin vers un fichier Markdown contenant l'objectif.
- `--config` (Optionnel) : Chemin alternatif vers un fichier config JSON (défaut : `config.json`).

---

## Fonctionnement Déterministe (Humain dans la boucle)

1. **Scan et Contexte** : L'assistant scanne l'arborescence et le contenu du dépôt cible (en ignorant les éléments définis dans le `.gitignore` et les exclusions standards comme `node_modules` ou `.git`).
2. **Phase 1 : Le Plan** : L'assistant génère un plan d'action au format Markdown et vous fournit un lien direct vers le fichier de plan. Vous pouvez :
   - Entrer `OK` pour valider et passer à l'étape suivante.
   - Entrer vos remarques pour demander une mise à jour du plan.
   - Entrer `exit` pour quitter la session.
3. **Phase 2 : Le Script** : L'assistant génère un script complet (`.sh` ou `.ps1`) et vous fournit le lien. Vous pouvez :
   - Entrer `OK` pour autoriser l'exécution.
   - Entrer vos remarques pour modifier le script.
   - Entrer `exit` pour quitter la session.
4. **Phase 3 : Exécution & Backup** : Avant de lancer le script, l'assistant copie tous les fichiers du dépôt dans un dossier de sauvegarde. Il exécute ensuite le script et vous affiche le journal d'exécution.
5. **Phase 4 : Validation / Annulation (Rollback)** : L'assistant vous demande si vous souhaitez valider les changements ou faire un retour arrière (restauration de la sauvegarde).
6. **Phase 5 : Archivage** : À la fin, un résumé de la session est créé et toute la session (contexte, plan, script, sauvegarde, résumé) est compressée dans un fichier `.zip` dans le dossier `sessions/`.

---

## Tests

Pour lancer la suite de tests automatisée afin de vérifier le bon fonctionnement de l'assistant :

```bash
python -m unittest test_neo_assistant.py
```
