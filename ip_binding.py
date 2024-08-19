# Скрипт проброса статических IP для OVPN

import json
import os
import argparse
import re
import ipaddress

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# функция смены местами любых пар ключ:значение в словаре d
swap_kv = lambda d: dict(map(lambda i,j : (j,i) , d.keys(),d.values()))

# Запись в файл со статическими IP нового словаря (d) json с 4 отступами от края + оповещение
def _update_json(d):
    with open(FIXED_IPS_JSON_PATH, "w") as f:
        json.dump(d, f, indent=4)
    print(f"{bcolors.OKBLUE}IP table updated{bcolors.ENDC}")

# читает список файлов в директории с клиентскими конфигами OVPN, парсит их до точки и проверяет, 
# есть ли конфиг с именем name + оповещение
def _check_ovpn_exists(name):
    ovpns = list(map(lambda x: x.split(".")[0], os.listdir(OVPN_DIR_ROOT)))
    if name not in ovpns:
        print(f"{bcolors.FAIL}Not found {name}.ovpn. Please, create it first.{bcolors.ENDC}")
        return False
    print(f"{bcolors.OKGREEN}Found {name}.ovpn{bcolors.ENDC}")
    return True

# проверяет, нее занят ли IP (список взят ранее из файла fixed_ips.json)
def _check_ip_is_not_forbidden(ip):
    subnet_forbidden_ips = fixed_ips
    if ip in subnet_forbidden_ips.values():
        print(f"{bcolors.FAIL}IP {ip} is already taken by {swap_kv(fixed_ips)[ip]}{bcolors.ENDC}")
        return False
    print(f"{bcolors.OKGREEN}IP {ip} is free{bcolors.ENDC}")
    return True

#проверяет, есть ли уже IP у данного name и возвращает его, если да
def _check_if_name_not_assigned(name):
    if name in fixed_ips.keys():
        ip = fixed_ips[name]
        print(f"{bcolors.WARNING}Name {bcolors.OKCYAN}\'{name}\'{bcolors.WARNING} already assigned to address {bcolors.OKCYAN}\'{ip}\'{bcolors.WARNING}. Are You shure You want to reassign it?{bcolors.ENDC}")
        ans = input(f"{bcolors.WARNING}(y/n): {bcolors.ENDC}")
        while ans.lower() not in ["y", "n"]:
            ans = input(f"{bcolors.WARNING}Choose from (y/n): {bcolors.ENDC} ")
        if ans.lower() == "y":
            return True
        print(f"{bcolors.WARNING}Nothing added{bcolors.ENDC}")
        return False
    print(f"{bcolors.OKGREEN}This name is not assigned to any static IP yet")
    return True

# 1. Проверяет, что IP из цифр 
# 2. Проверяет, что IP из 1-3 символов в блоке 
# 3. Режет IP по точкам, забирает все, кроме последнего блока и сверяет с адресом подсети
def _check_correct_ip(ip):
    for byte in ip.split("."):
        if not byte.isdigit():
            print(f"{bcolors.FAIL}Wrong IP format{bcolors.ENDC}")
            return False
    if not bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",ip)):
        print(f"{bcolors.FAIL}Wrong IP format{bcolors.ENDC}") 
        return False
    if ".".join(ip.split(".")[:-1]) != prefix:
        print(f"{bcolors.FAIL}Wrong gateway{bcolors.ENDC}") 
        return False
    return True

# Если в списке нет заданных name и IP и имя не занято -
# В клиентский файл задается команда, которая задает нужный статический IP для OVPN
# Клиенсткий файл новый, так что он просто переписывается, а не дополняется
def update_specific_name_ip(name, ip):
    if not _check_ovpn_exists(name) or not _check_ip_is_not_forbidden(ip) or not _check_if_name_not_assigned(name):
        return
    fixed_ips[name] = ip
    with open(os.path.join(CLIENT_DIR_ROOT, name), "w") as f:
        f.write(f"ifconfig-push {ip} 255.255.255.0")
    print(f"Added fixed adress {bcolors.OKGREEN}\'{ip}\'{bcolors.ENDC} for client {bcolors.OKGREEN}\'{name}\'{bcolors.ENDC}")
    _update_json(fixed_ips)

# берет список всех IP из файла, забирает из них последний блок после точки и складывает в список
# берет список чисел от 2 до 255 и убирает из него занятые IP из списка выше
# задает новый IP по первому свободному числу в списке
def update_single(name):
    subnet_fixed_nums = list(map(lambda x: int(x.split(".")[-1]), fixed_ips.values()))
    all_nums = list(range(2, 256))
    free_nums = list(set(all_nums)-set(subnet_fixed_nums))
    new_ip = f"{prefix}.{free_nums[0]}"
    print(f"{bcolors.OKGREEN}No ip from args, so {new_ip} will be assigned{bcolors.ENDC}")
    update_specific_name_ip(name, new_ip)
    
# собирает свободные IP
# забирает имена из файлов с клиентскими конфигами
# если список имен в fixed_ips совпадает со списком name клиентских файлов - пишет все ок
# если name нет в fixed_ips - присваивает ему первый свободный IP и срезает список на 1
# обновляет список IP и записывает его в файл
def auto_update_all_fixed_ips():
    subnet_fixed_nums = list(map(lambda x: int(x.split(".")[-1]), fixed_ips.values()))
    all_nums = list(range(2, 256))
    free_nums = list(set(all_nums)-set(subnet_fixed_nums))
    names = list(map(lambda x: x.split(".")[0], os.listdir(OVPN_DIR_ROOT)))
    if set(names) == set(fixed_ips.keys()):
        print(f"{bcolors.OKGREEN}All up-to-date{bcolors.ENDC}")
    for name in names:
        if name not in fixed_ips:
            fixed_ips[name] = f"{prefix}.{free_nums[0]}"
            new_ip = fixed_ips[name]
            free_nums = free_nums[1:]
            with open(os.path.join(CLIENT_DIR_ROOT, name), "w") as f:
                f.write(f"ifconfig-push {new_ip} 255.255.255.0")
            _update_json(fixed_ips)
            print(f"Added fixed adress {bcolors.OKGREEN}\'{new_ip}\'{bcolors.ENDC} for client {bcolors.OKGREEN}\'{name}\'{bcolors.ENDC}")
    with open(FIXED_IPS_JSON_PATH, "w") as f:
        json.dump(fixed_ips, f, indent=4)  

# удаление нужного IP из списка + удалить клиентский файл
def remove_by_name(name):
    if name in fixed_ips.keys():
        ip = fixed_ips[name]
        print(f"{bcolors.WARNING}Name {bcolors.OKCYAN}\'{name}\'{bcolors.WARNING} assigned to address {bcolors.OKCYAN}\'{ip}\'{bcolors.WARNING}. Are You shure You want to remove it?{bcolors.ENDC}")
        ans = input(f"{bcolors.WARNING}(y/n): {bcolors.ENDC}")
        while ans.lower() not in ["y", "n"]:
            ans = input(f"{bcolors.WARNING}Choose from (y/n): {bcolors.ENDC} ")
        if ans.lower() == "y":
            ip_rm = fixed_ips.pop(name)
            _update_json(fixed_ips)
            print(f"{bcolors.OKGREEN}Removed {name} from ip table. It'had ip {ip_rm}{bcolors.ENDC}")
            os.remove(os.path.join(CLIENT_DIR_ROOT, name))
            print(f"{bcolors.OKGREEN}Removed {name} client file{bcolors.ENDC}")
            os.remove(os.path.join(OVPN_DIR_ROOT, name+".ovpn"))
            print(f"{bcolors.OKGREEN}Removed {name} .ovpn file{bcolors.ENDC}")
            print(f"{bcolors.FAIL}Dont forget to remove it with openvpn-install.sh{bcolors.ENDC}")
            return True
        print(f"{bcolors.WARNING}Nothing removed{bcolors.ENDC}")
    print(f"{bcolors.OKGREEN}This name is not assigned to any static IP yet")

        
# update_single("gnss_bs")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bind name of .ovpn config to static IP addres')
    parser.add_argument('--remove', type=str, default='', help="If true will remove config with given name")
    parser.add_argument('--name', type=str,  help='Name of generated ovpn config')
    parser.add_argument('--client_ip_dir', type=str, default='/etc/openvpn/client/', help='where client static IPs files are')
    parser.add_argument('--client_config_dir', type=str, default='/openvpn/clients', help='Where client .ovpn configs are')
    parser.add_argument('--subnet', type=str, default='10.2.1.1', help='OVPN subnet')
    parser.add_argument('--ip', type=str, help='Desirable ip to bind to')
    args = parser.parse_args()
    CLIENT_DIR_ROOT=args.client_ip_dir
    OVPN_DIR_ROOT=args.client_config_dir
    GATEWAY=str(ipaddress.IPv4Address(args.subnet)+1)
    FIXED_IPS_JSON_PATH = f'{CLIENT_DIR_ROOT}static_ip_table.json'

    # забираем файл со статическими IP и переводим его в json

    if not os.path.exists(FIXED_IPS_JSON_PATH):
        with open(FIXED_IPS_JSON_PATH, "w") as f:
            f.write('{}')
    with open(FIXED_IPS_JSON_PATH, "r") as f:
        fixed_ips = json.load(f)
        
    prefix = ".".join(GATEWAY.split(".")[:-1])
    p = list(map(int, GATEWAY.split("."))) 

    if not args.remove:
        if args.name is None:
            auto_update_all_fixed_ips()
        else:
            if args.ip is None:
                update_single(args.name)
            else:
                if _check_correct_ip(args.ip):
                    update_specific_name_ip(args.name, args.ip)
        print(f"Do  \'sudo systemctl restart openvpn*\' to apply changes")
    else:
        remove_by_name(args.remove)

