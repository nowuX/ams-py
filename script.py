import importlib
import json
import os
import subprocess
import sys
from urllib.request import urlopen

import requests

# Disable Colors until i fix windows console issue with ANSI
# class Colors:
#     GREEN = '\033[92m'
#     YELLOW = '\033[93m'
#     RED = '\033[91m'
#     LIGHT_GREEN = "\033[1;32m"
#     LIGHT_GRAY = "\033[0;37m"
#     BOLD = '\033[1m'
#     END = '\033[0m'
class Colors:
    GREEN = ''
    YELLOW = ''
    RED = ''
    LIGHT_GREEN = ''
    LIGHT_GRAY = ''
    BOLD = ''
    END = ''

def exception_handler(name: str, exception: Exception):
    first_line = f'{Colors.RED}Something failed in: {Colors.BOLD}{name}{Colors.END}\n'
    second_line = f'{Colors.LIGHT_GRAY}Exception caught:\n{Colors.END}{exception}'
    print(first_line + second_line)


def simple_yes_no(q: str, default_no=True):
    while True:
        choices = ' [y/N]:{} '.format(Colors.END) if default_no else ' [Y/n]:{} '.format(Colors.END)
        ans = str(input(Colors.BOLD + q + choices)).lower().strip()
        if ans[:1] == '':
            return False if default_no else True
        else:
            if ans[:1] == 'yes' or ans[:1] == 'y':
                return True
            if ans[:1] == 'no' or ans[:1] == 'n':
                return False
        print('{} is invalid, please try again...'.format(ans))


def mk_folder():
    folder = input('{}Enter the server name:{} '.format(Colors.BOLD, Colors.END))
    if os.path.exists(folder):
        print('Folder already exists!')
        exit(1)
    else:
        try:
            print('{}mkdir {}...{}'.format(Colors.LIGHT_GRAY, folder, Colors.END))
            os.mkdir(folder)
            os.chdir(folder)
        except OSError as err:
            exception_handler(mk_folder.__name__, err)
            exit(1)


def mcdr_setup():
    # Check MCDR pip package installation status and init MCDR environment
    try:
        importlib.import_module('mcdreforged')
        print('{}MCDReforged packaged detected{}'.format(Colors.LIGHT_GRAY, Colors.END))
    except ImportError:
        print('{}MCDReforged packaged NOT detected, proceed to install...{}'.format(Colors.YELLOW, Colors.END))
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'mcdreforged'])
    subprocess.run(['python', '-m', 'mcdreforged', 'init'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Server loader
    os.chdir('server')
    option = server_loader()
    os.chdir('..')
    # Edit config.yml
    with open('config.yml', 'r') as f:
        data = f.readlines()
        data[19] = 'start_command: java -Xms1G -Xmx2G -jar {}.jar nogui\n'.format(option)
    with open('config.yml', 'w') as f:
        f.writelines(data)
    return option


def post_mcdr(jar_file: str):
    # Put loader.jar name in config.yml
    with open('config.yml', 'r') as f:
        data = f.readlines()
    data[19] = 'start_command: java -Xms1G -Xmx2G -jar {}.jar nogui\n'.format(jar_file)
    with open('config.yml', 'w') as f:
        f.writelines(data)
    # Set nickname of the owner (not necessary)
    with open('permission.yml', 'r') as f:
        data = f.readlines()
    nickname = str(input('{}What is the nickname of the server owner? [Skip]:{} '.format(Colors.BOLD, Colors.END)))
    if nickname:
        print('{}Nickname to set: {}{}'.format(Colors.LIGHT_GRAY, nickname, Colors.END))
        data[13] = '- {}\n'.format(nickname)
        with open('permission.yml', 'w') as f:
            f.writelines(data)


def launch_scripts(cmd: str, python_linux=False):
    with open('start.bat', 'w') as f:
        f.write('{}\n'.format(cmd))
    if sys.platform == 'linux':
        if python_linux:
            cmd = cmd.replace('python', 'python3')
        with open('start.sh', 'w') as f:
            f.write('#!/usr/bin/env bash\n{}\n'.format(cmd))
        subprocess.run(['chmod', '+x', 'start.sh'])


def post_server(jar_file: str, mcdr: bool):
    if mcdr:
        post_mcdr(jar_file)
        launch_scripts('python -m mcdreforged start', True)
    else:
        launch_scripts('java -Xms1G -Xmx2G -jar {}.jar nogui'.format(jar_file))
    if simple_yes_no('Do you want to start the server and set EULA=true?'):
        try:
            print('{}Starting server for the first time... may take some time{}'.format(Colors.LIGHT_GRAY, Colors.END))
            if sys.platform == 'win32':
                subprocess.run(['start.bat'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == 'linux':
                subprocess.run(['./start.sh'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print('{}First time server start complete!{}'.format(Colors.LIGHT_GREEN, Colors.END))
            # Set EULA=true
            if mcdr:
                os.chdir('server')
            with open('eula.txt', 'r') as f:
                data = f.readlines()
            data[2] = 'eula=true\n'
            with open('eula.txt', 'w') as f:
                f.writelines(data)
            print('{}EULA set to true!{}'.format(Colors.LIGHT_GREEN, Colors.END))
        except (Exception, FileNotFoundError) as err:
            exception_handler(post_server.__name__, err)
            exit(1)


def vanilla_loader():
    url = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'
    response = urlopen(url)
    version_manifest_json = json.loads(response.read())
    versions = version_manifest_json["versions"]
    while True:
        try:
            mc = str(input('{}Which version do you want to use?:{} '.format(Colors.BOLD, Colors.END)))
            print('{}Option selected: {}{}'.format(Colors.LIGHT_GRAY, mc, Colors.END))
            print('{}Downloading vanilla loader...{}'.format(Colors.LIGHT_GRAY, Colors.END))
            for s in range(len(versions)):
                if versions[s]['id'] == mc:
                    url = versions[s]['url']
                    break
            response = urlopen(url)
            version_json = json.loads(response.read())
            server_url = str(version_json['downloads']['server']['url'])
            server_file = str(list(server_url.split('/'))[6])
            r = requests.get(server_url, allow_redirects=True)
            open(server_file, 'wb').write(r.content)
            print('{}Download of vanilla loader complete!{}'.format(Colors.LIGHT_GREEN, Colors.END))
            return server_file
        except requests.exceptions.RequestException as err:
            exception_handler(vanilla_loader.__name__, err)


def fabric_loader():
    # Download installer and check java
    url = 'https://maven.fabricmc.net/net/fabricmc/fabric-installer/0.10.2/fabric-installer-0.10.2.jar'
    fabric_file = str(list(url.split('/'))[7])
    try:
        subprocess.run(['java', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        r = requests.get(url, allow_redirects=True)
        open(fabric_file, 'wb').write(r.content)
    except (FileNotFoundError, requests.exceptions.RequestException) as err:
        exception_handler(fabric_loader.__name__, err)
        exit(1)

    # Input minecraft version and loader version (not necessary)
    while True:
        mc = str(
            input('{}Which version of Minecraft do you want to use? [latest]:{} '.format(Colors.BOLD, Colors.END)))
        print('{}Option selected: {}{}'.format(Colors.LIGHT_GRAY, mc, Colors.END))
        fabric = str(
            input('{}Which version of fabric loader do you want to use? [latest]:{} '.format(Colors.BOLD, Colors.END)))
        print('{}Option selected: {}{}'.format(Colors.LIGHT_GRAY, fabric, Colors.END))
        try:
            print('{}Downloading fabric loader...{}'.format(Colors.LIGHT_GRAY, Colors.END))
            if not mc and not fabric:
                subprocess.run(
                    ['java', '-jar', fabric_file, 'server', '-downloadMinecraft'],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if mc and not fabric:
                subprocess.run(
                    ['java', '-jar', fabric_file, 'server', '-mcversion', mc, '-downloadMinecraft'],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if not mc and fabric:
                subprocess.run(
                    ['java', '-jar', fabric_file, 'server', '-loader', fabric, '-downloadMinecraft'],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if mc and fabric:
                subprocess.run(
                    ['java', '-jar', fabric_file, 'server', '-mcversion', mc, '-loader', fabric, '-downloadMinecraft'],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print('{}Download of fabric loader complete!{}'.format(Colors.LIGHT_GREEN, Colors.END))
            os.remove(fabric_file)
            return 'fabric-server-launch'
        except subprocess.CalledProcessError as err:
            exception_handler(fabric_loader.__name__, err)


def server_loader():
    print(
        """{0}Which loader do you want to use?{1}
        \033[1m1)\033[0m Vanilla
        \033[1m2)\033[0m Fabric
        \033[1m3)\033[0m Soon [WIP]""".format(Colors.BOLD, Colors.END)
    )
    while True:
        try:
            option = int(input('{}Select a option:{} '.format(Colors.BOLD, Colors.END)))
            # Vanilla
            if option == 1:
                print('{}Option selected: Vanilla{}'.format(Colors.LIGHT_GRAY, Colors.END))
                return vanilla_loader()
            # Fabric
            elif option == 2:
                print('{}Option selected: Fabric{}'.format(Colors.LIGHT_GRAY, Colors.END))
                return fabric_loader()
            # Exit
            elif option == 3:
                print('Closing program')
                exit(0)
        except ValueError:
            print('Invalid option, please try again...')


if __name__ == '__main__':
    # Making server folder and enter inside
    mk_folder()
    # MCDR Setup and Loader Setup
    mcdr_status = False
    loader = int
    if simple_yes_no('{}Do you want to use MCDR?'.format(Colors.BOLD)):
        loader = mcdr_setup()
        mcdr_status = True
    else:
        server_loader()
    # Extra post server config
    post_server(loader, mcdr_status)
    print('{}{}› Script done!{}'.format(Colors.GREEN, Colors.BOLD, Colors.END))
    exit(0)
