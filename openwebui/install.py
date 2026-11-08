"""Installe ou met à jour la fonction MedAssist dans Open WebUI et en fait l'interface par défaut.

Installe aussi l'habillage : logo et icônes (openwebui/static, générés par make_branding.py), feuille de style,
fiches des deux modèles (avatar, description, suggestions), suggestions de départ et bandeau d'information.

À lancer avec le Python d'Open WebUI, serveur ARRÊTÉ (la configuration est lue au démarrage) :
  %USERPROFILE%\\open-webui\\venv\\Scripts\\python.exe openwebui\\install.py [--keep-ollama-models]
Dossier d'installation : variable MEDASSIST_ROOT (défaut %USERPROFILE%\\open-webui) ; DATA_DIR = ce dossier\\data.

--keep-ollama-models : garde les modèles Ollama bruts visibles dans la liste (par défaut, seuls
MedAssist Pro et MedAssist Patient apparaissent ; réactivable dans Admin > Paramètres > Connexions).
"""
import asyncio
import base64
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

FUNCTION_ID = "medassist"
SOURCE = Path(__file__).resolve().parent / "medassist_pipe.py"
STATIC = SOURCE.parent / "static"  # logo, icônes, custom.css (voir make_branding.py)

DISCLAIMER = ("MedAssist est une aide à la décision, 100 % locale : rien ne quitte ce PC. Il ne remplace ni le "
              "jugement clinique ni les sources officielles (RCP, recommandations) : vérifiez toute information "
              "qui engage une décision.")

# Suggestions de départ (page d'accueil) : [titre, sous-titre], question envoyée
SUGGESTIONS = [
    (["Antibiothérapie", "exacerbation de BPCO : indication, molécule, durée"],
     "Exacerbation aiguë de BPCO chez un adulte : quand prescrire un antibiotique, lequel et pour quelle durée ?"),
    (["Cystites récidivantes", "antibioprophylaxie : options et doses"],
     "Antibioprophylaxie des cystites récidivantes de la femme : quelles options, à quelle dose et pour combien de temps ?"),
    (["Radiographie thoracique", "joignez l'image pour une double lecture"],
     "Lisez cette radiographie thoracique de face (image jointe) : anomalies, degré de confiance et limites."),
    (["Vérifier un score", "critères, interprétation, limites"],
     "Score de Wells pour l'embolie pulmonaire : critères, interprétation et limites ?"),
    (["Expliquer un résultat", "en termes simples, pour un patient"],
     "Expliquez-moi simplement ce qu'est l'HbA1c et ce que signifie un résultat à 7,5 %."),
    (["Interaction médicamenteuse", "précautions et surveillance"],
     "Un patient sous warfarine doit prendre de l'amoxicilline : interactions et précautions ?"),
]

# Fiches des modèles (la description s'affiche sur deux lignes au plus sous le nom : rester court)
MODELS = {
    "pro": dict(
        name="MedAssist Pro", avatar="medassist_pro.png",
        description="Professionnels de santé · réponses sourcées HAS et OMS, relecture automatique, "
                    "double lecture des radios thoraciques · 100 % local",
        suggestions=SUGGESTIONS[:4] + [SUGGESTIONS[5]], tags=["Professionnels"]),
    "patient": dict(
        name="MedAssist Patient", avatar="medassist_patient.png",
        description="Patients · explications claires et repères pour savoir quand consulter, sans jargon ni "
                    "diagnostic · ne remplace pas votre médecin",
        suggestions=[
            SUGGESTIONS[4],
            (["Mon traitement", "à quoi faire attention pendant une antibiothérapie"],
             "On m'a prescrit de l'amoxicilline : à quoi faut-il faire attention pendant le traitement ?"),
            (["Fièvre de l'enfant", "quand consulter rapidement"],
             "Mon enfant de 3 ans a 39 °C depuis hier : quels signes doivent m'amener à consulter rapidement ?"),
            (["Comprendre une maladie", "en termes simples"],
             "Qu'est-ce qu'une BPCO et comment évolue-t-elle ?"),
        ],
        tags=["Patients"]),
}
MEDASSIST_ROOT = Path(os.environ.get("MEDASSIST_ROOT", Path.home() / "open-webui"))
DATA_DIR = Path(os.environ.setdefault("DATA_DIR", str(MEDASSIST_ROOT / "data")))
ROOT = DATA_DIR.parent
PORT = 8080

# Open WebUI exige sa clé secrète : celle de start-medassist.ps1 (ROOT), sinon celle d'un ancien lancement
if not os.environ.get("WEBUI_SECRET_KEY"):
    for key_file in (ROOT / ".webui_secret_key", Path.cwd() / ".webui_secret_key", Path.home() / ".webui_secret_key"):
        if key_file.exists():
            os.environ["WEBUI_SECRET_KEY"] = key_file.read_text()
            break


def server_running():
    """La configuration est lue au démarrage d'Open WebUI : l'installer serveur lancé n'aurait pas d'effet visible."""
    import socket
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


async def install_function():
    from open_webui.models.functions import FunctionForm, FunctionMeta, Functions
    from open_webui.models.users import Users
    from open_webui.utils.plugin import load_function_module_by_id, replace_imports

    content = replace_imports(SOURCE.read_text(encoding="utf-8"))
    module, ftype, frontmatter, _ = await load_function_module_by_id(FUNCTION_ID, content=content)
    assert ftype == "pipe", f"type inattendu : {ftype}"

    form = FunctionForm(id=FUNCTION_ID, name="MedAssist", content=content,
                        meta=FunctionMeta(description=frontmatter.get("description"), manifest=frontmatter))
    if await Functions.get_function_by_id(FUNCTION_ID):
        await Functions.update_function_by_id(FUNCTION_ID, {"content": content, "meta": form.meta.model_dump()})
        action = "mise à jour"
    else:
        admins = [u for u in (await Users.get_users())["users"] if u.role == "admin"]
        if not admins:
            sys.exit("Aucun compte admin : crée d'abord ton compte sur http://localhost:8080")
        await Functions.insert_new_function(admins[0].id, ftype, form, module=module)
        action = "installée"
    await Functions.update_function_by_id(FUNCTION_ID, {"is_active": True})
    print(f"Fonction {FUNCTION_ID} {action} et activée ({frontmatter.get('version')}).")


def set_config(keep_ollama):
    values = {
        "ui.default_models": f"{FUNCTION_ID}.pro",
        "ui.default_locale": "fr-FR",
        "ui.prompt_suggestions": [{"title": title, "content": content} for title, content in SUGGESTIONS],
        "ui.banners": [{"id": "medassist-disclaimer", "type": "info", "title": "", "content": DISCLAIMER,
                        "dismissible": True, "timestamp": int(time.time())}],
    }
    if not keep_ollama:
        values["ollama.enable"] = False
    db = sqlite3.connect(DATA_DIR / "webui.db")
    with db:
        for key, value in values.items():
            db.execute('INSERT INTO config ("key", value, updated_at) VALUES (?, ?, ?) '
                       'ON CONFLICT("key") DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at',
                       (key, json.dumps(value), int(time.time())))
    db.close()
    for key, value in values.items():
        print(f"config {key} = {str(value)[:80]}")


async def install_models():
    """Fiches des deux modèles du pipe : avatar, description, suggestions. Sans elles, Open WebUI affiche son logo."""
    from open_webui.models.models import ModelForm, ModelMeta, ModelParams, Models
    from open_webui.models.users import Users

    admins = [u for u in (await Users.get_users())["users"] if u.role == "admin"]
    for suffix, spec in MODELS.items():
        avatar = base64.b64encode((STATIC / spec["avatar"]).read_bytes()).decode()
        meta = ModelMeta(
            profile_image_url=f"data:image/png;base64,{avatar}",
            description=spec["description"],
            suggestion_prompts=[{"title": title, "content": content} for title, content in spec["suggestions"]],
            tags=[{"name": t} for t in spec["tags"]],
            # « citations » doit rester actif : désactivé, l'interface efface les renvois [n] du texte
            capabilities={"vision": True, "file_upload": False, "web_search": False, "image_generation": False,
                          "code_interpreter": False, "usage": False, "status_updates": True},
        )
        form = ModelForm(id=f"{FUNCTION_ID}.{suffix}", name=spec["name"], meta=meta, params=ModelParams(), is_active=True)
        if await Models.get_model_by_id(form.id):
            await Models.update_model_by_id(form.id, form)
        else:
            await Models.insert_new_model(form, admins[0].id)
        print(f"Fiche du modèle {form.id} ({spec['name']}) enregistrée.")


def static_source_dir():
    """Dossier d'où Open WebUI recopie, à CHAQUE démarrage, les fichiers statiques (logo, favicon, custom.css) vers
    le dossier servi : remplacer les fichiers servis ne suffit pas, il faut remplacer ceux-ci."""
    import open_webui
    pkg = Path(open_webui.__file__).resolve().parent
    for candidate in (pkg / "frontend" / "static", pkg / "static" / "static"):
        if candidate.is_dir():
            return candidate
    sys.exit("Dossier statique d'Open WebUI introuvable : version non prise en charge")


def copy_static():
    """Logo, icônes et feuille de style MedAssist dans le paquet Open WebUI. Les originaux sont conservés une fois
    dans static-openwebui-original (restauration : les recopier). À refaire après une mise à jour d'Open WebUI,
    qui les remet en place. Licence Open WebUI : remplacement du logo permis en dessous de 50 utilisateurs."""
    import shutil
    dst = static_source_dir()
    backup = ROOT / "static-openwebui-original"
    backup.mkdir(exist_ok=True)
    n = 0
    for f in STATIC.iterdir():
        if not f.is_file():
            continue
        if (dst / f.name).exists() and not (backup / f.name).exists():
            shutil.copy2(dst / f.name, backup / f.name)
        shutil.copy2(f, dst / f.name)
        n += 1
    print(f"Habillage : {n} fichiers MedAssist copiés dans {dst} (originaux dans {backup})")


def copy_runtime():
    """Copie le lecteur radio et le script de lancement à côté d'Open WebUI : ils ne dépendent plus de ce dossier."""
    import shutil
    project = SOURCE.parent.parent
    target = DATA_DIR.parent / "radiology"
    target.mkdir(exist_ok=True)
    for name in ("cxr_model.py", "service.py", "calibrate_local.py"):
        shutil.copy2(project / "radiology" / name, target / name)
    # Ne pas écraser une calibration locale déjà faite sur le site
    cal_src = json.loads((project / "radiology" / "calibration.json").read_text(encoding="utf-8"))
    cal_dst = target / "calibration.json"
    if cal_dst.exists():
        local = json.loads(cal_dst.read_text(encoding="utf-8")).get("local")
        if local:
            cal_src["local"] = local
    cal_dst.write_text(json.dumps(cal_src, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.copy2(project / "start-medassist.ps1", ROOT / "start-medassist.ps1")
    shutil.copy2(project / "doctor.py", ROOT / "doctor.py")
    print(f"Lecteur radio copié dans {target} ; lancement : {ROOT / 'start-medassist.ps1'} ; contrôle : {ROOT / 'doctor.py'}")
    # Base documentaire : l'outil d'indexation ; les PDF (docs) et l'index restent ceux de l'utilisateur
    kb = DATA_DIR.parent / "knowledge"
    (kb / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(project / "knowledge" / "ingest.py", kb / "ingest.py")
    print(f"Base documentaire : déposez vos PDF dans {kb / 'docs'} puis lancez {kb / 'ingest.py'}")


if __name__ == "__main__":
    if server_running() and "--force" not in sys.argv:
        sys.exit(f"Open WebUI écoute sur le port {PORT} : arrêtez-le (Ctrl+C dans sa fenêtre) avant d'installer, "
                 "puis relancez start-medassist.ps1. (--force pour passer outre.)")
    asyncio.run(install_function())
    asyncio.run(install_models())
    set_config("--keep-ollama-models" in sys.argv)
    copy_static()
    copy_runtime()
