import importlib
import json
import logging
import os
import re
import subprocess
import sys
from urllib.request import urlopen

import requests
from colorlog import ColoredFormatter

mojang_versions_manifest = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'
loader_url = 'https://maven.fabricmc.net/net/fabricmc/fabric-installer/0.11.0/fabric-installer-0.11.0.jar'
python: str  # Global python program name
mcdr = "mcdreforged"  # Global mcdr package name


class ScriptLogger(logging.Logger):
    def __init__(self):
        super().__init__('Script')
        formatter = ColoredFormatter(
            "[%(name)s] [%(asctime)s] %(log_color)s%(levelname)-8s%(reset)s: %(message)s",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
                'INPUT': 'blue',
            },
            datefmt="%H:%M:%S",
            reset=True
        )
        self.INPUT = 24
        logging.addLevelName(self.INPUT, 'INPUT')
        self.console_handler = logging.StreamHandler()
        self.console_handler.setFormatter(formatter)
        self.console_handler.setLevel(logging.DEBUG)
        self.addHandler(self.console_handler)
        self.setLevel(logging.DEBUG)


def input_logger(msg: str):
    _input_logger = ScriptLogger()
    _input_logger.console_handler.terminator = ''
    _input_logger.console_handler.setFormatter(
        ColoredFormatter(
            "[%(name)s] %(log_color)s%(levelname)-5s%(reset)s: %(white)s%(message)s%(reset)s",
                         log_colors={'INPUT': 'blue'}))
    _input_logger.setLevel('INPUT')
    _input_logger.log(_input_logger.INPUT, msg)


def subprocess_logger(args, stderr: bool = True, stdout: bool = True, exit_in_error=True):
    sp_logger = ScriptLogger()
    sp_logger.name = "~"
    sp_logger.console_handler.setFormatter(
        ColoredFormatter("%(log_color)s%(name)s%(reset)s %(message)s",
                         log_colors={'INFO': 'bold', 'ERROR': 'bold_red'},
                         reset=True))
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if stdout:
        with process.stdout as p:
            for line in iter(p.readline, b''):
                sp_logger.info(line.decode('utf-8').strip())
    if stderr:
        with process.stderr as p:
            for line in iter(p.readline, b''):
                sp_logger.error(line.decode('utf-8').strip())
    process.wait()
    if process.returncode != 0 and exit_in_error:
        logger.error('Something failed in subprocess execution')
        exit(1)


def check_environment():
    logger.info('Check environment...')
    global python
    match sys.platform:
        case "win32":
            python = "python"
        case "linux":
            python = "python3"
        case _:
            logger.error('OS {} is currently not supported'.format(sys.platform))
            exit(0)

    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 10):
        print(sys.version_info.major)
        print(sys.version_info.minor)
        logger.warning('Python 3.10+ is needed')
        exit(0)

    try:
        subprocess_logger(['java', '-version'], stderr=False)
    except FileNotFoundError:
        logger.warning('Java is needed')
        logger.error('System can\'t find java')
        exit(0)

    try:
        importlib.import_module(mcdr)
    except ImportError:
        logger.error('MCDReforged packaged not detected')
        logger.warning('Installing MCDReforged...')
        subprocess_logger([python, '-m', 'pip', 'install', mcdr])


def simple_yes_no(q: str, default_no=True) -> bool:
    while True:
        choices = ' [y/N]: ' if default_no else ' [Y/n]: '
        input_logger(q + choices)
        ans = input().lower().strip()
        match ans[:1]:
            case '':
                return False if default_no else True
            case 'yes' | 'y':
                return True
            case 'no' | 'n':
                return False
            case _:
                logger.info('{} is an invalid answer, please try again'.format(ans))


def mk_folder():
    input_logger('Enter the server folder name [minecraft_server]: ')
    folder: str = re.sub(r'\W', '', input().replace(' ', '_'))
    if not folder:
        folder = 'minecraft_server'
    if os.path.exists(folder):
        logger.warning('Folder already exists')
        exit(0)
    else:
        try:
            logger.info('Making folder "{}"...'.format(folder))
            os.mkdir(folder)
            os.chdir(folder)
        except OSError:
            logger.error('Something failed while the folder was being created')
            exit(1)


def vanilla_loader() -> str:
    logger.info('Vanilla Loader setup')
    while True:
        input_logger('Which minecraft version do you want to use? [latest]: ')
        mc: str = input().strip()
        if re.match(r'[\d.]', mc) or not mc:
            logger.info('Version selected: {}'.format(mc))
            logger.info('Downloading vanilla loader...')
            try:
                response = urlopen(mojang_versions_manifest)
                versions_json = json.loads(response.read())['versions']
                url: str = ''
                if not mc:
                    response = urlopen(mojang_versions_manifest)
                    mc = json.loads(response.read())['latest']['release']
                for s in range(len(versions_json)):
                    if versions_json[s]['id'] == mc:
                        url = versions_json[s]['url']
                        break
                response = urlopen(url)
                version_json = json.loads(response.read())
                server_url: str = version_json['downloads']['server']['url']
                server_file = list(server_url.split('/'))[6]
                r = requests.get(server_url, allow_redirects=True)
                open(server_file, 'wb').write(r.content)
                logger.info('Vanilla loader download complete')
                return server_file.replace('.jar', '')
            except requests.exceptions.RequestException as err:
                logger.error('Something failed: {}'.format(err))
                exit(1)
        else:
            logger.warning('Version provided contain invalid characters')


def fabric_loader() -> str:
    logger.info('Fabric Loader setup')
    fabric = str(list(loader_url.split('/'))[7])
    latest: str = 'latest'
    try:
        logger.info("Downloading fabric loader...")
        r = requests.get(loader_url, allow_redirects=True)
        open(fabric, 'wb').write(r.content)
        while True:
            input_logger('Which version of Minecraft do you want to use? [latest]: ')
            mc: str = input().strip()
            input_logger('Which version of Fabric Loader do you want to use? [latest]: ')
            loader: str = input().strip()

            if mc and bool(re.match(r'[^\d.]', mc)):
                logger.warning('Minecraft version provided contain invalid characters')
                continue
            if loader and bool(re.match(r'[^\d.]', loader)):
                logger.warning('Loader version provided contain invalid characters')
                continue
            logger.info('Minecraft version selected: {}'.format(latest if not mc else mc))
            logger.info('Fabric loader version selected: {}'.format(latest if not loader else loader))

            try:
                logger.info('Installing server resources...')
                if not mc and not loader:
                    subprocess_logger(['java', '-jar', fabric, 'server', '-downloadMinecraft'])
                elif mc and not loader:
                    subprocess_logger(['java', '-jar', fabric, 'server', '-mcversion', mc, '-downloadMinecraft'])
                elif not mc and loader:
                    subprocess_logger(['java', '-jar', fabric, 'server', '-loader', loader, '-downloadMinecraft'])
                elif mc and loader:
                    subprocess_logger(
                        ['java', '-jar', fabric, 'server', '-mcversion', mc, '-loader', loader, '-downloadMinecraft'])
                logger.info('The download is finished')
                os.remove(fabric)
                return 'fabric-server-launch'
            except requests.exceptions.RequestException as err:
                logger.error('Something failed: {}'.format(err))
                exit(1)
    except requests.exceptions.RequestException as err:
        logger.error('Something failed: {}'.format(err))
        exit(1)


def loader_setup(loader: int):
    match loader:
        case 1:
            return vanilla_loader()
        case 2:
            return fabric_loader()
        case _:
            logger.error('Invalid loader option {}'.format(loader))


def launch_scripts(cmd: str):
    logger.info('Creating launch scripts...')
    try:
        with open('start.bat', 'w') as f:
            f.write('@echo off\n{}\n'.format(cmd))
        with open('start.sh', 'w') as f:
            f.write('#!\\bin\\bash\n{}\n'.format(cmd))
        if sys.platform == 'linux':
            subprocess_logger(['chmod', '+x', 'start.sh'])
    except FileNotFoundError as err:
        logger.error('Something failed while generating the scripts: {}'.format(err))
        exit(1)


def mcdr_setup(loader: int):
    logger.info('MCDR setup')
    subprocess_logger([python, '-m', mcdr, 'init'])
    os.chdir('server')
    jar_name = loader_setup(loader)
    os.chdir('..')
    try:
        with open('config.yml', 'r') as f:
            data = f.readlines()
            data[19] = 'start_command: {}\n'.format(start_command(jar_name))
        with open('config.yml', 'w') as f:
            f.writelines(data)
        input_logger('Set the nickname of the server owner? [Skip]: ')
        nickname = input().strip()
        if nickname:
            logger.info('Nickname to set: {}'.format(nickname))
            with open('permission.yml', 'r') as f:
                data = f.readlines()
                data[13] = '- {}\n'.format(nickname)
            with open('permission.yml', 'w') as f:
                f.writelines(data)
    except FileNotFoundError as err:
        logger.error('Something failed: {}'.format(err))
        exit(1)


def start_command(jar_name: str) -> str:
    return 'java -Xms1G -Xmx2G -jar {}.jar nogui'.format(jar_name)


def post_setup(jar_file: str = None, mcdr_environment: bool = False):
    if mcdr_environment:
        launch_scripts('{} -m mcdreforged start'.format(python))
    else:
        launch_scripts(start_command(jar_file))
    if simple_yes_no('Do you want to start the server and set EULA=true?'):
        logger.info('Starting the server for the first time')
        logger.info('May take some time...')
        try:
            if mcdr_environment:
                with open('config.yml', 'r') as f:
                    data = f.readlines()
                    data[77] = 'disable_console_thread: true\n'
                with open('config.yml', 'w') as f:
                    f.writelines(data)
            match sys.platform:
                case 'win32':
                    subprocess_logger([r'start.bat'])
                case 'linux':
                    subprocess_logger([r'./start.sh'])
                case _:
                    raise Exception
            logger.info('First time server start complete')
            if mcdr_environment:
                with open('config.yml', 'r') as f:
                    data = f.readlines()
                    data[77] = 'disable_console_thread: false\n'
                with open('config.yml', 'w') as f:
                    f.writelines(data)
                os.chdir('server')
            with open('eula.txt', 'r') as f:
                data = f.readlines()
                data[2] = 'eula=true\n'
            with open('eula.txt', 'w') as f:
                f.writelines(data)
            logger.info('EULA set to true complete')
        except (FileNotFoundError, Exception) as err:
            logger.error('Something failed: {}'.format(err))
            exit(1)


def server_loader() -> int:
    logger.info("Which loader do you want to use?")
    logger.info("\t1 - Vanilla")
    logger.info("\t2 - Fabric")
    logger.info("\t3 - Close script")
    while True:
        input_logger("Select a option: ")
        try:
            option = int(input())
            if option in range(1, 3):
                return option
            elif option == 3:
                logger.info('Close script...')
                return exit(0)
            else:
                logger.warning('Input is not within the options')
        except ValueError:
            logger.warning('Input is not a integer')


def main():
    logger.info('Auto server script is starting up')
    check_environment()
    mk_folder()
    loader = server_loader()
    if simple_yes_no('Do you want to use MCDR?'):
        mcdr_setup(loader)
        post_setup(mcdr_environment=True)
    else:
        post_setup(jar_file=loader_setup(loader))
    logger.info('Script done')
    return


if __name__ == '__main__':
    logger = ScriptLogger()  # Create global logger
    sys.exit(main())
