"""Main python script"""
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

MOJANG_VERSIONS_MANIFEST: str = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'
LOADER_URL: str = 'https://maven.fabricmc.net/net/fabricmc/fabric-installer/0.11.0/fabric-installer-0.11.0.jar'
MINECRAFT: str = ''
MCDR: str = 'mcdreforged'  # Global mcdr package name


class ScriptLogger(logging.Logger):
    """Creates a Logger for script CLI output logging"""

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
        self.input = 24
        logging.addLevelName(self.input, 'INPUT')
        self.console_handler = logging.StreamHandler()
        self.console_handler.setFormatter(formatter)
        self.console_handler.setLevel(logging.DEBUG)
        self.addHandler(self.console_handler)
        self.setLevel(logging.DEBUG)


def input_logger(msg: str):
    """Creates a logger for input()"""
    _input_logger = ScriptLogger()
    _input_logger.console_handler.terminator = ''
    _input_logger.console_handler.setFormatter(
        ColoredFormatter(
            "[%(name)s] %(log_color)s%(levelname)-5s%(reset)s: %(white)s%(message)s%(reset)s",
            log_colors={'INPUT': 'blue'}))
    _input_logger.setLevel('INPUT')
    _input_logger.log(_input_logger.input, msg)


def subprocess_logger(args, stderr: bool = True, stdout: bool = True, exit_in_error: bool = True):
    """Creates a logger for catch all subprocess.Popen()"""
    sp_logger = ScriptLogger()
    sp_logger.name = "~"
    sp_logger.console_handler.setFormatter(
        ColoredFormatter("%(log_color)s%(name)s%(reset)s %(message)s",
                         log_colors={'INFO': 'bold', 'ERROR': 'bold_red'},
                         reset=True))
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        if stdout:
            with process.stdout as _stdout:
                for line in iter(_stdout.readline, b''):
                    sp_logger.info(line.decode('utf-8').strip())
        if stderr:
            with process.stderr as _stderr:
                for line in iter(_stderr.readline, b''):
                    sp_logger.error(line.decode('utf-8').strip())
        process.wait()
        if process.returncode != 0 and exit_in_error:
            logger.error('Something failed in subprocess execution')
            sys.exit(1)


def check_environment() -> str:
    """Check all script requirements"""
    logger.info('Check environment...')
    py_cmd: str
    match sys.platform:
        case "win32":
            py_cmd = "python"
        case "linux":
            py_cmd = "python3"
        case _:
            logger.error('OS %s is currently not supported', sys.platform)
            sys.exit(0)
    major_version, minor_version = sys.version_info.major, sys.version_info.minor
    if major_version < 3 or (major_version == 3 and minor_version < 10):
        logger.warning('Python 3.10+ is needed')
        sys.exit(0)

    try:
        subprocess_logger(['java', '-version'], stderr=False)
    except FileNotFoundError:
        logger.warning('Java is needed')
        logger.error('System can\'t find java')
        sys.exit(0)

    try:
        importlib.import_module(MCDR)
    except ImportError:
        logger.error('MCDReforged packaged not detected')
        logger.warning('Installing MCDReforged...')
        subprocess_logger([py_cmd, '-m', 'pip', 'install', MCDR])
    return py_cmd


def simple_yes_no(question: str, default_no=True) -> bool:
    """Make a simple yes or no question"""
    while True:
        choices = ' [y/N]: ' if default_no else ' [Y/n]: '
        input_logger(question + choices)
        ans = input().lower().strip()
        match ans[:1]:
            case '':
                return False if default_no else default_no
            case 'yes' | 'y':
                return True
            case 'no' | 'n':
                return False
            case _:
                logger.info('%s is an invalid answer, please try again', ans)


def mk_folder():
    """Make server folder"""
    input_logger('Enter the server folder name [minecraft_server]: ')
    folder: str = re.sub(r'\W', '', input().replace(' ', '_'))
    if not folder:
        folder = 'minecraft_server'
    if os.path.exists(folder):
        logger.warning('Folder already exists')
        sys.exit(0)
    else:
        try:
            logger.info('Making folder: %s...', folder)
            os.mkdir(folder)
            os.chdir(folder)
        except OSError:
            logger.error('Something failed while the folder was being created')
            sys.exit(1)


def vanilla_loader() -> str:
    """Install minecraft vanilla loader"""
    logger.info('Vanilla Loader setup')
    while True:
        input_logger('Which minecraft version do you want to use? [latest]: ')
        version: str = input().strip()

        tmp = version.split('.')
        major, minor = int(tmp[1]), int(tmp[2]) if len(tmp) == 3 else 0
        is_invalid = major < 2 or (major == 2 and minor < 5)
        if is_invalid:
            logger.warning('This version is currently unsupported by the script')
            return sys.exit(1)

        if re.match(r'[\d.]', version) or not version:
            logger.info('Version selected: %s', version)
            logger.info('Downloading vanilla loader...')
            try:
                with urlopen(MOJANG_VERSIONS_MANIFEST) as response:
                    versions_json = json.loads(response.read())['versions']
                url: str = ''
                if not version:
                    with urlopen(MOJANG_VERSIONS_MANIFEST) as response:
                        version = json.loads(response.read())['latest']['release']
                for i in range(len(versions_json)):
                    if versions_json[i]['id'] == version:
                        url = versions_json[i]['url']
                        break
                with urlopen(url) as response:
                    version_json = json.loads(response.read())
                server_url: str = version_json['downloads']['server']['url']
                server_file = list(server_url.split('/'))[6]
                response = requests.get(server_url, allow_redirects=True)
                with open(server_file, 'wb') as file:
                    file.write(response.content)
                logger.info('Vanilla loader download complete')
                _globals = globals()
                _globals['MINECRAFT'] = version
                return server_file.replace('.jar', '')
            except requests.exceptions.RequestException as err:
                logger.error('Something failed: %s', err)
                sys.exit(1)
        else:
            logger.warning('Version provided contain invalid characters')


def fabric_loader() -> str:
    """Install minecraft fabric loader"""
    logger.info('Fabric Loader setup')
    fabric = str(list(LOADER_URL.split('/'))[7])
    latest: str = 'latest'
    logger.info("Downloading fabric loader...")
    try:
        response = requests.get(LOADER_URL, allow_redirects=True)
        with open(fabric, 'wb') as file:
            file.write(response.content)
        while True:
            input_logger('Which version of Minecraft do you want to use? [latest]: ')
            minecraft: str = input().strip()
            input_logger('Which version of Fabric Loader do you want to use? [latest]: ')
            fabric_version: str = input().strip()

            if minecraft and bool(re.match(r'[^\d.]', minecraft)):
                logger.warning('Minecraft version provided contain invalid characters')
                continue
            if fabric_version and bool(re.match(r'[^\d.]', fabric_version)):
                logger.warning('Loader version provided contain invalid characters')
                continue
            logger.info('Minecraft version selected: %s', latest if not minecraft else minecraft)
            logger.info('Fabric loader version selected: %s', latest if not fabric_version else fabric_version)

            try:
                logger.info('Installing server resources...')
                if not minecraft and not fabric_version:
                    subprocess_logger(['java', '-jar', fabric, 'server', '-downloadMinecraft'])
                elif minecraft and not fabric_version:
                    subprocess_logger(['java', '-jar', fabric, 'server', '-mcversion', minecraft, '-downloadMinecraft'])
                elif not minecraft and fabric_version:
                    subprocess_logger(
                        ['java', '-jar', fabric, 'server', '-loader', fabric_version, '-downloadMinecraft'])
                elif minecraft and fabric_version:
                    subprocess_logger(
                        ['java', '-jar', fabric, 'server', '-mcversion', minecraft, '-loader', fabric_version,
                         '-downloadMinecraft'])
                logger.info('The download is finished')
                os.remove(fabric)
                _globals = globals()
                _globals['MINECRAFT'] = minecraft
                return 'fabric-server-launch'
            except requests.exceptions.RequestException as err:
                logger.error('Something failed: %s', err)
            except ValueError as err:
                logger.error('Something failed: %s', err)
    except requests.exceptions.RequestException as err:
        logger.error('Something failed: %s', err)
        sys.exit(1)


def loader_setup(loader: int) -> str:
    """Call loader function"""
    match loader:
        case 1:
            return vanilla_loader()
        case 2:
            return fabric_loader()
        case _:
            logger.error('Invalid loader option %s', loader)
            sys.exit(1)


def launch_scripts(cmd: str):
    """Create and write launch script for server launch"""
    logger.info('Creating launch scripts...')
    try:
        with open('start.bat', 'w', encoding='utf-8') as file:
            file.write(f'@echo off\n{cmd}\n')
        with open('start.sh', 'w', encoding='utf-8') as file:
            file.write(f'#!\\bin\\bash\n{cmd}\n')
        if sys.platform == 'linux':
            subprocess_logger(['chmod', '+x', 'start.sh'])
    except FileNotFoundError as err:
        logger.error('Something failed while generating the scripts: %s', err)
        sys.exit(1)


def mcdr_setup(loader: int, py_cmd: str):
    """Install and configure MCDReforged"""
    logger.info('MCDR setup')
    subprocess_logger([py_cmd, '-m', MCDR, 'init'])
    os.chdir('server')
    jar_name = loader_setup(loader)
    os.chdir('..')
    try:
        with open('config.yml', 'r', encoding='utf-8') as file:
            data = file.readlines()
            data[19] = f'start_command: {start_command(jar_name)}\n'
        with open('config.yml', 'w', encoding='utf-8') as file:
            file.writelines(data)
        input_logger('Set the nickname of the server owner? [Skip]: ')
        nickname = input().strip()
        if nickname:
            logger.info('Nickname to set: %s', nickname)
            with open('permission.yml', 'r', encoding='utf-8') as file:
                data = file.readlines()
                data[13] = f'- {nickname}\n'
            with open('permission.yml', 'w', encoding='utf-8') as file:
                file.writelines(data)
    except FileNotFoundError as err:
        logger.error('Something failed: %s', err)
        sys.exit(1)


def start_command(jar_name: str) -> str:
    """return a string within server jar name"""
    return f'java -Xms1G -Xmx2G -jar {jar_name}.jar nogui'


def post_setup(is_mcdr: bool = False, python: str = None, jar_file: str = None):
    """Create server launch scripts and set EULA=true
    :param jar_file: Minecraft server jar name
    :param is_mcdr: Validate if is a MCDReforged environment
    :param python: python standard command"""
    if is_mcdr:
        launch_scripts(f'{python} -m mcdreforged start')
    else:
        launch_scripts(start_command(jar_file))

    tmp = MINECRAFT.split('.')
    major, minor = int(tmp[1]), int(tmp[2]) if len(tmp) == 3 else 0
    is_invalid = major < 7 or (major == 7 and minor < 10)
    if is_invalid:
        logger.warning('Minecraft version too old, EULA does not exists ')
        return

    if simple_yes_no('Do you want to start the server and set EULA=true?'):
        logger.info('Starting the server for the first time')
        logger.info('May take some time...')
        try:
            if is_mcdr:
                with open('config.yml', 'r', encoding='utf-8') as file:
                    data = file.readlines()
                    data[77] = 'disable_console_thread: true\n'
                with open('config.yml', 'w', encoding='utf-8') as file:
                    file.writelines(data)
            match sys.platform:
                case 'win32':
                    subprocess_logger([r'start.bat'])
                case 'linux':
                    subprocess_logger([r'./start.sh'])
                case _:
                    raise Exception
            logger.info('First time server start complete')
            if is_mcdr:
                with open('config.yml', 'r', encoding='utf-8') as file:
                    data = file.readlines()
                    data[77] = 'disable_console_thread: false\n'
                with open('config.yml', 'w', encoding='utf-8') as file:
                    file.writelines(data)
                os.chdir('server')
            with open('eula.txt', 'r', encoding='utf-8') as file:
                data = file.readlines()
                data[2] = 'eula=true\n'
            with open('eula.txt', 'w', encoding='utf-8') as file:
                file.writelines(data)
            logger.info('EULA set to true complete')
        except FileNotFoundError as err:
            logger.error('Something failed: %s', err)
            sys.exit(1)


def server_loader() -> int:
    """Choose the server loader"""
    logger.info("Which loader do you want to use?")
    logger.info("\t1 - Vanilla")
    logger.info("\t2 - Fabric")
    logger.info("\t3 - Close script")
    while True:
        input_logger("Select a option: ")
        option = input().lower().strip()
        match option:
            case '1' | 'vanilla':
                return 1
            case '2' | 'fabric':
                return 2
            case '3' | 'exit':
                logger.info('Closing script...')
                return sys.exit(0)
        logger.warning('Input is not within the options')


def main():
    """Initialize the script"""
    logger.info('Auto server script is starting up')
    python = check_environment()
    mk_folder()
    loader = server_loader()
    if simple_yes_no('Do you want to use MCDR?'):
        mcdr_setup(loader, python)
        post_setup(is_mcdr=True, python=python)
    else:
        post_setup(python=python, jar_file=loader_setup(loader))
    logger.info('Script done')
    return 0


if __name__ == '__main__':
    logger = ScriptLogger()  # Create global logger
    sys.exit(main())
