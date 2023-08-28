import requests
import json
import os
from shutil import rmtree
from ipaddress import IPv4Interface, IPv6Interface

class Icinga2_Netbox:
    api_devices = "/api/dcim/devices/"
    api_virtuals = "/api/virtualization/virtual-machines/"



    def __init__(self, netbox_url, netbox_token):
        self.headers = headers = {'Authorization':'Token ' + netbox_token,
           'Content-Type':'application/json',
           'Accept': 'application/json; indent=4'
        }
        self.netbox_token = netbox_token
        self.netbox_url = netbox_url
        self.load_monitored_devices()
        self.load_monitored_virtuals()
        self.iterate_nodes_and_find_out_monitoring()
        self.generate_host_config_files()
        self.generate_zone_config_files()


    def load_monitored_devices(self):
        d_response = requests.get(url=self.netbox_url + self.api_devices + '?tag=icinga2', 
                                  headers=self.headers)
        self.monitored_devices = d_response.json()['results']

    def load_monitored_virtuals(self):
        d_response = requests.get(url=self.netbox_url + self.api_virtuals + '?tag=icinga2',
                                  headers=self.headers)
        self.monitored_virtuals = d_response.json()['results']

    def iterate_nodes_and_find_out_monitoring(self):

        self.icinga_client_list = []
        self.nrpe_list = []
        self.nrpe_windows_list = []
        self.icinga_windows_list = []
        self.undefined_default_list = []

        print('BLACKLIST:')
        print(self.return_blacklist())
        print(' ')

        for node in self.monitored_devices:
            if node['name'] in self.return_blacklist():
                continue
            if 'icinga2-client' in node['tags']:
                self.icinga_client_list.append(node)
            elif 'nrpe-client' in node['tags']:
                self.nrpe_list.append(node)
            elif 'nrpe-windows' in node['tags']:
                self.nrpe_windows_list.append(node)
            elif 'icinga2-windows' in node['tags']:
                self.icinga_windows_list.append(node)
            else:
                self.undefined_default_list.append(node)

        for node in self.monitored_virtuals:
            if node['name'] in self.return_blacklist():
                continue
            if 'icinga2-client' in node['tags']:
                self.icinga_client_list.append(node)
            elif 'nrpe-client' in node['tags']:
                self.nrpe_list.append(node)
            elif 'nrpe-windows' in node['tags']:
                self.nrpe_windows_list.append(node)
            elif 'icinga2-windows' in node['tags']:
                self.icinga_windows_list.append(node)
            else:
                self.undefined_default_list.append(node)

    #blacklist

    def generate_host_config_files(self):
        rmtree('/etc/icinga2/zones.d/icinga2-thp2.core.ignum.cz/hosts.dynamic', ignore_errors=True)
        rmtree('/etc/icinga2/zones.d/icinga2-nrpe.core.ignum.cz/hosts.dynamic', ignore_errors=True)
        os.makedirs('/etc/icinga2/zones.d/icinga2-thp2.core.ignum.cz/hosts.dynamic',
        0o755, exist_ok=True)
        os.makedirs('/etc/icinga2/zones.d/icinga2-nrpe.core.ignum.cz/hosts.dynamic',
        0o755, exist_ok=True)
        for node in self.icinga_client_list:
            self.generate_host_config_file(node, 'icinga2-thp2.core.ignum.cz')

        for node in self.nrpe_list:
            self.generate_host_config_file(node, 'icinga2-nrpe.core.ignum.cz')

        for node in self.nrpe_windows_list:
            self.generate_host_config_file(node, 'icinga2-nrpe.core.ignum.cz')

        for node in self.icinga_windows_list:
            self.generate_host_config_file(node, 'icinga2-thp2.core.ignum.cz')

        for node in self.undefined_default_list:
            self.generate_host_config_file(node, 'icinga2-thp2.core.ignum.cz')


    def generate_zone_config_files(self):
        rmtree('/etc/icinga2/zones.d/icinga2-thp2.core.ignum.cz/zones.dynamic', ignore_errors=True)
        os.makedirs('/etc/icinga2/zones.d/icinga2-thp2.core.ignum.cz/zones.dynamic',
        0o755, exist_ok=True)
        for node in self.icinga_client_list:
            self.generate_host_zone_file(node, 'icinga2-thp2.core.ignum.cz')

        for node in self.icinga_windows_list:
            self.generate_host_zone_file(node, 'icinga2-thp2.core.ignum.cz')


    def generate_host_config_file(self, node, satellite):
        if (not node['primary_ip4']) and (not node['primary_ip6']):
            print('Tento host nemá přiřazenou žádnou IP adresu.')
            print(node['name'])
            print('')
        else:
            name = node['name']
            url_head, sep, tail = name.partition('.')
            icinga_template = self.find_out_host_template(node)
            conf_host_template = open('templates/icingahost.tmpl', 'r').read()
            host_config = open(
                '/etc/icinga2/zones.d/' + satellite + '/hosts.dynamic/' + url_head + '.conf', 'w'
                )
            address_string = self.make_address_string(node)
            variables_string = self.make_variables_string(node)
            host_config.write(
                    conf_host_template % (
                        node['name'], icinga_template,
                         str(address_string), variables_string
                        )
                    )


    def generate_host_zone_file(self, node, satellite):
        name = node['name']
        url_head, sep, tail = name.partition('.')
        hostzone_template = open('templates/hostzonefile.tmpl', 'r').read()
        hostzone_config = open('/etc/icinga2/zones.d/' + satellite + '/zones.dynamic/' + url_head + '-zone.conf', 'w')
        hostzone_config.write(
                hostzone_template % (
                    node['name'], node['name'], node['name'], node['name'], satellite
                    )
                )


    def find_out_host_template(self, node):
        if 'ispconfig' in node['tags']:
            return 'ispconfig31-host'
        elif 'lhc-www' in node['tags']:
            return 'php-lhc-server'
        elif 'kvm' in node['tags']:
            return 'kvm-host'
        elif 'nrpe-windows' in node['tags']:
            return 'windows-host-nrpe'
        elif 'icinga2-windows' in node['tags']:
            return 'windows-host-icinga'
        else:
            unknown_template_warning = 'Tento host nemá nastavenou žádnou šablonu, kvm ani ispc,'
            unknown_template_warning += ' takže mu bude automaticky přiřazena šablona generic-host'
            unknown_template_warning += ' bez speciálních icinga a nrpe checků.'
            print(unknown_template_warning)
            print(node['name'])
            print('')
            return 'generic-host'

    def make_address_string(self, node):
        if node['primary_ip4'] and node['primary_ip6']:
            # print(node['primary_ip4']['address'])
            # print(node['primary_ip6']['address'])
            ipv4_interface = IPv4Interface(node['primary_ip4']['address'])
            ipv6_interface = IPv6Interface(node['primary_ip6']['address'])
            address_string = 'address = \"' + str(ipv4_interface.ip) + '\"'
            address_string += '\n' + '  address6 = ' + '\"' + str(ipv6_interface.ip) + '\"'
        elif (not node['primary_ip4']) and node['primary_ip6']:
            # print(node['primary_ip6']['address'])
            ipv6_interface = IPv6Interface(node['primary_ip6']['address'])
            address_string = 'address6 = ' + '\"' + str(ipv6_interface.ip) + '\"'
        elif node['primary_ip4'] and (not node['primary_ip6']):
            # print(node['primary_ip4']['address'])
            ipv4_interface = IPv4Interface(node['primary_ip4']['address'])
            address_string = 'address = \"' + str(ipv4_interface.ip) + '\"'
        elif (not node['primary_ip4']) and (not node['primary_ip6']):
            print('Tento host nemá přiřazenou žádnou IP adresu.')
            print(node['name'])
            print('')
            address_string = ''

        return address_string

    def make_variables_string(self, node):
        variables_list = []
        variables_string = ""
        if 'aacraid' in node['tags']:
            variables_list.append('vars.aac_raid = true')

        if 'mdadm' in node['tags']:
            variables_list.append('vars.mdadm = true')

        if 'hpraid' in node['tags']:
            variables_list.append('vars.hpacucli = true')

        for counter, variable in enumerate(variables_list):
            if counter > 0:
                variables_string += '\n' + '  '

            variables_string += variable

        if not variables_string:
            variables_string = ' '

        return variables_string

    def return_blacklist(self):
        blacklist_file = open('blacklist', 'r').readlines()
        blacklist = []

        for bl in blacklist_file:
            bl = bl.replace('\n', '')
            blacklist.append(bl)

        return blacklist

generator = Icinga2_Netbox('https://netbox.core.ignum.cz', '6e105d54510491126e938e65260aaf6b2f3a24b7')
