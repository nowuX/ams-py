import importlib
import json
import os.path
import re
import subprocess
import sys

import requests
import urllib3

LOADERS: list = ['Vanilla', 'Fabric', 'Forge', 'Quilt', 'Carpet 1.12', 'Paper']
PYTHON_CMD: str = ''
SERVER_JAR: str = ''
QUILT_URL = 'https://maven.quiltmc.org/repository/release/org/quiltmc/quilt-installer/latest/quilt-installer-latest.jar'
PAPER_URL: str = 'https://api.papermc.io/v2/projects/paper/'
FORGE_URL: str = 'https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json'
FORGE_URL2: str = 'https://maven.minecraftforge.net/net/minecraftforge/forge/'
FABRIC_URL: str = 'https://maven.fabricmc.net/net/fabricmc/fabric-installer/0.11.0/fabric-installer-0.11.0.jar'
CARPET_112: str = 'https://gitlab.com/Xcom/carpetinstaller/uploads/24d0753d3f9a228e9b8bbd46ce672dbe/carpetInstaller.jar'
MOJANG_VERSIONS_MANIFEST: str = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'


def sp(args: str, exit_in_error=False):
    try:
        with subprocess.Popen(args.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            with process.stdout as stdout:
                for line in iter(stdout.readline, b''):
                    print(f'[STDOUT] {line.decode("utf-8").strip()}')
            with process.stderr as stderr:
                for line in iter(stderr.readline, b''):
                    print(f'[STDERR] {line.decode("utf-8").strip()}')
            process.wait()
            if process.returncode != 0 and exit_in_error:
                print('!! Something failed in subprocess execution')
                raise SystemError
    except (FileNotFoundError, SystemError):
        print(f'!! Looks like system can\'t find that program: {args[0]}')
        sys.exit(1)


def simple_yes_no(question: str, default_no=True) -> bool:
    while True:
        choose = ' [y/N]: ' if default_no else ' [Y/n]: '
        ans = input('→ ' + question + choose).lower().strip()
        match ans[0] if ans else ans[:1]:
            case '':
                return not bool(default_no)
            case 'yes' | 'y':
                return True
            case 'no' | 'n':
                return False
            case _:
                print(f'{ans} is an invalid answer, yes or no required')


def check_environment() -> str:
    sp('java -version')
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 10):
        print('!! Python 3.10+ is needed')
        sys.exit(0)
    match sys.platform:
        case 'win32':
            return 'python'
        case 'linux':
            return 'python3'
        case _:
            print(f'!! {sys.platform} is currently not supported as OS')
            sys.exit(0)


def mk_folder(folder: str):
    try:
        if os.path.exists(folder):
            print(f'!! Folder "{folder}" already exists')
            sys.exit(0)
        os.mkdir(folder)
        os.chdir(folder)
    except OSError as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)


def server_loader() -> int:
    print('→ Which loader do you want to use?')
    for key, value in enumerate(LOADERS):
        print(f' {key + 1} | {value}')
    while True:
        option: str = input('→ Select a option: ').lower().strip()
        for key, value in enumerate(LOADERS):
            if str(key + 1) == option or str(value).lower() == option:
                return key
        print(f'{option} is an invalid answer, a valid index o loader name is needed')


def vanilla_loader(minecraft: str):
    print('> Vanilla loader setup')
    tmp = minecraft.split('.')
    major, minor = int(tmp[1]), int(tmp[2]) if len(tmp) == 3 else 0
    is_invalid = major < 2 or (major == 2 and minor < 5)
    if is_invalid:
        print(f'!! Version {minecraft} is currently unsupported by the script')
        sys.exit(1)
    if re.match(r'[\d.]', minecraft):
        try:
            http = urllib3.PoolManager()
            resp: urllib3.response.HTTPResponse = http.request('GET', MOJANG_VERSIONS_MANIFEST)
            versions_json: dict = json.loads(resp.data.decode('utf-8'))['versions']
            for index, version in enumerate(versions_json):
                if version['id'] == minecraft:
                    url: str = version['url']
                    resp = http.request('GET', url)
                    version_json: dict = json.loads(resp.data.decode('utf-8'))
                    server_url: str = version_json['downloads']['server']['url']
                    # Download server.jar and write in disk
                    response: requests.models.Response = requests.get(server_url, allow_redirects=True)
                    server_file: str = list(server_url.split('/'))[6]
                    with open(server_file, 'wb') as file:
                        file.write(response.content)
                    globals()['SERVER_JAR'] = server_file
                    print('> Vanilla server download complete')
                    break
                if index == len(versions_json) - 1:
                    print('!! Version not found in Mojang manifest')
                    break
        except (urllib3.exceptions.MaxRetryError, requests.exceptions.RequestException) as err:
            print(f'!! Something failed:\n\t{err}')
            sys.exit(1)
    else:
        print(f'!! Version provided: {minecraft} is invalid')


def fabric_loader(minecraft: str):
    print('> Fabric loader setup')
    try:
        response = requests.get(FABRIC_URL, allow_redirects=True)
        installer: str = list(FABRIC_URL.split('/'))[7]
        with open(installer, 'wb') as file:
            file.write(response.content)
        if minecraft and re.match(r'[\d.]', minecraft):
            print(f'!! Version provided: {minecraft} is invalid')
            return
        sp(f'java -jar {installer} server -mcversion {minecraft} -downloadMinecraft')
        globals()['SERVER_JAR'] = 'fabric-server-launch.jar'
        print('> Fabric server download complete')
        os.remove(installer)
    except (urllib3.exceptions.MaxRetryError, requests.exceptions.RequestException, OSError) as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)


def forge_loader(minecraft: str):
    print('> Quilt loader setup')
    try:
        http = urllib3.PoolManager()
        resp: urllib3.response.HTTPResponse = http.request('GET', FORGE_URL)
        versions_json: dict = json.loads(resp.data.decode('utf-8'))['promos']
        for index, version_raw in enumerate(versions_json):
            version_raw: str = version_raw.replace('-latest', '').replace('-recommended', '')
            if version_raw == minecraft:
                if simple_yes_no('> Do you want to use latest forge build? [latest]', default_no=False):
                    version = f'{version_raw}-latest'
                else:
                    version = f'{version_raw}-recommended'
                print(f'> Using forge: {version}')
                build = versions_json[version]
                version_build = f'{version_raw}-{build}'
                server_file = f'forge-{version_build}-installer.jar'
                server_url = f'{FORGE_URL2}{version_build}/{server_file}'
                response = requests.get(server_url, allow_redirects=True)
                with open(server_file, 'wb') as file:
                    file.write(response.content)
                sp(f'java -jar {server_file} --installServer')
                print('> Forge server download complete')
                os.remove(f'{server_file}.log')
                os.remove(server_file)
                break
            if index == len(versions_json) - 1:
                print('!! Version not found in Forge')
                break
    except (urllib3.exceptions.MaxRetryError, requests.exceptions.RequestException, OSError) as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)
    except KeyError as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(2)


def quilt_loader(minecraft: str):
    print('> Quilt loader setup')
    try:
        response = requests.get(QUILT_URL, allow_redirects=True)
        installer: str = list(QUILT_URL.split('/'))[9]
        with open(installer, 'wb') as file:
            file.write(response.content)
        if minecraft and re.match(r'[^\d.]', minecraft):
            print(f'!! Version provided: {minecraft} is invalid')
            return
        sp(f'java -jar {installer} install server {minecraft} --install-dir={os.getcwd()} --download-server')
        globals()['SERVER_JAR'] = 'quilt-server-launch.jar'
        print('> Quilt server download complete')
        os.remove(installer)
    except (requests.exceptions.RequestException, OSError) as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)


def carpet112_setup():
    print('> Carpet 1.12 setup')
    try:
        response = requests.get(CARPET_112, allow_redirects=True)
        installer: str = CARPET_112.split('/')[7]
        with open(installer, 'wb') as file:
            file.write(response.content)
        sp(f'java -jar {installer}')
        os.chdir('update')
        carpet_file: str = [file.replace('zip', 'jar') for file in os.listdir(os.getcwd()) if file.endswith('.zip')][0]
        import shutil
        shutil.move(carpet_file, '..')
        os.chdir('..')
        shutil.rmtree('update')
        globals()['SERVER_JAR'] = carpet_file
        print('> Carpet 1.12 download complete')
        os.remove(installer)
    except (requests.exceptions.RequestException, OSError) as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)


def paper_loader(minecraft: str):
    print('> Paper loader setup')
    try:
        http = urllib3.PoolManager()
        resp: urllib3.response.HTTPResponse = http.request('GET', PAPER_URL)
        versions_json: dict = json.loads(resp.data.decode('utf-8'))['versions']
        for index, version in enumerate(versions_json):
            if version == minecraft:
                print('> Paper minecraft version found!')
                temp_url = f'{PAPER_URL}versions/{minecraft}/builds/'
                resp: urllib3.response.HTTPResponse = http.request('GET', temp_url)
                version_json: dict = json.loads(resp.data.decode('utf-8'))
                print(f'{version_json=}')
                print(f'{type(version_json)=}')
                build: str = version_json['builds'][-1]['build']
                server_file: str = version_json['builds'][-1]['downloads']['application']['name']
                server_url: str = f'{temp_url}{build}/downloads/{server_file}/'
                response = requests.get(server_url, allow_redirects=True)
                with open(server_file, 'wb') as file:
                    file.write(response.content)
                globals()['SERVER_JAR'] = server_file
                print('> Paper server download complete')
                break
            if index == len(versions_json) - 1:
                print('!! Version not found in PaperMC')
                break
    except (urllib3.exceptions.MaxRetryError, requests.exceptions.RequestException) as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)


def loader_setup(loader: int, mc: str):
    # _LOADERS = {'Vanilla': 0, 'Fabric': 1, 'Forge': 2, 'Quilt': 3, 'Carpet 1.12': 4, 'Paper': 5}
    try:
        match loader:
            case 0:
                vanilla_loader(mc)
            case 1:
                fabric_loader(mc)
            case 2:
                forge_loader(mc)
            case 3:
                quilt_loader(mc)
            case 4:
                carpet112_setup()
            case 5:
                paper_loader(mc)
            case _:
                raise OSError
    except OSError as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)


def mcdr_setup(loader: int, mc: str, is_forge: bool):
    def start_command(jar_name: str) -> str:
        return f'java -Xms1G -Xmx2G -jar {jar_name}.jar nogui'

    mcdr: str = 'mcdreforged'
    try:
        importlib.import_module(mcdr)
    except ImportError:
        print(f'!! {mcdr} package is required')
        if simple_yes_no('Do you want to autoinstall this package?', default_no=False):
            print('> Update pip packages')
            sp(f'{PYTHON_CMD} -m pip install --upgrade pip setuptools wheel')
            print(f'> Installing {mcdr} package')
            sp(f'{PYTHON_CMD} -m pip install {mcdr}')
    try:
        sp(f'{PYTHON_CMD} -m {mcdr} init')
        os.chdir('server')
        loader_setup(loader, mc)
        os.chdir('..')
        # start_command edit
        config_file = 'config.yml'
        with open(config_file, 'r', encoding='utf-8') as file:
            data = file.readlines()
            if not is_forge:
                data[19] = f'start_command: {start_command(SERVER_JAR)}\n'
            else:
                print(f'=== Edit {config_file}::start_command if you use linux ===')
                data[19] = f'start_command: run.bat\n'
        with open(config_file, 'w', encoding='utf-8') as file:
            file.writelines(data)
        # permission.yml set owner name
        nickname: str = input('→ Do you want to set the server owner in MCDR? [Skip]: ').strip()
        if nickname:
            print(f'> Nickname to set {nickname}')
            perm_file = 'permission.yml'
            with open(perm_file, 'r', encoding='utf-8') as file:
                data = file.readlines()
                data[13] = f'- {nickname}\n'
            with open(perm_file, 'w', encoding='utf-8') as file:
                file.writelines(data)
    except OSError as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)


def post_setup(is_mcdr: bool, mc_version: str, is_forge: bool):
    try:
        def launch_scripts(cmd: str):
            print('> Creating launch scripts')
            with open('start.bat', 'w', encoding='utf-8') as _file:
                _file.write(f'@echo off\n{cmd}\n')
            with open('start.sh', 'w', encoding='utf-8') as _file:
                _file.write(f'#!\\bin\\bash\n{cmd}\n')
            if sys.platform == 'linux':
                sp('chmod +x start.sh')

        if is_mcdr:
            launch_scripts(f'{PYTHON_CMD} -m mcdreforged start')
        else:
            if not is_forge:
                launch_scripts(f'java -Xms1G -Xmx2G -jar {SERVER_JAR} nogui')
            else:
                launch_scripts('run.bat')
        tmp = mc_version.split('.')
        # 1.18.2 => major=18, minor=2 || 1.16 => major=16, minor=0
        major, minor = int(tmp[1]), int(tmp[2]) if len(tmp) == 3 else 0
        is_invalid = major < 7 or (major == 7 and minor < 10)
        if not is_invalid:
            if simple_yes_no('→ Do you want to start the server and set EULA=true?'):
                print('> Starting the server for the first time\nMay take some time...')

                def console_thread(status: bool):
                    with open('config.yml', 'r', encoding='utf-8') as _file:
                        _data = _file.readlines()
                        _data[77] = f'disable_console_thread: {"true" if status else "false"}\n'
                    with open('config.yml', 'w', encoding='utf-8') as _file:
                        _file.writelines(_data)

                if is_mcdr:
                    console_thread(True)
                match sys.platform:
                    case 'win32':
                        sp(r'start.bat')
                    case 'linux':
                        sp(r'./start.sh')
                print('> First time server startup complete')
                if is_mcdr:
                    console_thread(False)
                    os.chdir('server')

                with open('eula.txt', 'r', encoding='utf-8') as file:
                    data = file.readlines()
                    data[2] = 'eula=true\n'
                with open('eula.txt', 'w', encoding='utf-8') as file:
                    file.writelines(data)
                if is_mcdr:
                    os.chdir('..')
                print('> EULA file set to True')
        else:
            print("> Minecraft version too old, doesn't exists")
    except (OSError, FileNotFoundError) as err:
        print(f'!! Something failed:\n\t{err}')
        sys.exit(1)


def main():
    print('> Server script is starting up!')
    # ENVIRONMENT CHECK
    globals()['PYTHON_CMD'] = check_environment()
    # SERVER FOLDER NAME
    server_folder: str = re.sub(r'\W', '', input('→ Server folder name [mc_server]: ').replace(' ', '_'))

    server_folder = server_folder if server_folder else 'mc_server'
    is_mcdr: bool = simple_yes_no('Dp you want to use MCDR?')
    loader: int = server_loader()
    # CHECK IF IS FORGE
    is_forge: bool = LOADERS[loader] == 'Forge'
    if is_forge:
        print('> Some features are disable due Forge loader')

    # MINECRAFT VERSION
    def get_last_release() -> str:
        http = urllib3.PoolManager()
        resp: urllib3.response.HTTPResponse = http.request('GET', MOJANG_VERSIONS_MANIFEST)
        return json.loads(resp.data.decode('utf-8'))['latest']['release']

    mc_version: str = re.sub(r'[^\d.]', '', input('→ Which minecraft version do you want to use? [latest]: ').strip())
    mc_version = mc_version if mc_version else get_last_release()
    # LOGIC OF THE SCRIPT
    mk_folder(server_folder)
    match is_mcdr:
        case True:
            mcdr_setup(loader, mc_version, is_forge)
        case False:
            loader_setup(loader, mc_version)
    post_setup(is_mcdr, mc_version, is_forge)


if __name__ == '__main__':
    sys.exit(main())
