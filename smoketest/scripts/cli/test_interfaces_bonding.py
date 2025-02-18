#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import unittest

from base_interfaces_test import BasicInterfaceTest

from vyos.ifconfig import Section
from vyos.ifconfig.interface import Interface
from vyos.configsession import ConfigSessionError
from vyos.util import get_interface_config
from vyos.util import read_file

class BondingInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._test_dhcp = True
        cls._test_ip = True
        cls._test_ipv6 = True
        cls._test_ipv6_pd = True
        cls._test_ipv6_dhcpc6 = True
        cls._test_mtu = True
        cls._test_vlan = True
        cls._test_qinq = True
        cls._base_path = ['interfaces', 'bonding']
        cls._mirror_interfaces = ['dum21354']
        cls._members = []

        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            cls._members = os.environ['TEST_ETH'].split()
        else:
            for tmp in Section.interfaces('ethernet'):
                if not '.' in tmp:
                    cls._members.append(tmp)

        cls._options['bond0'] = []
        for member in cls._members:
            cls._options['bond0'].append(f'member interface {member}')
        cls._interfaces = list(cls._options)

        # call base-classes classmethod
        super(cls, cls).setUpClass()

    def test_add_single_ip_address(self):
        super().test_add_single_ip_address()

        for interface in self._interfaces:
            slaves = read_file(f'/sys/class/net/{interface}/bonding/slaves').split()
            self.assertListEqual(slaves, self._members)

    def test_vif_8021q_interfaces(self):
        super().test_vif_8021q_interfaces()

        for interface in self._interfaces:
            slaves = read_file(f'/sys/class/net/{interface}/bonding/slaves').split()
            self.assertListEqual(slaves, self._members)

    def test_bonding_remove_member(self):
        # T2515: when removing a bond member the previously enslaved/member
        # interface must be in its former admin-up/down state. Here we ensure
        # that it is admin-up as it was admin-up before.

        # configure member interfaces
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

        self.cli_commit()

        # remove single bond member port
        for interface in self._interfaces:
            remove_member = self._members[0]
            self.cli_delete(self._base_path + [interface, 'member', 'interface', remove_member])

        self.cli_commit()

        # removed member port must be admin-up
        for interface in self._interfaces:
            remove_member = self._members[0]
            state = Interface(remove_member).get_admin_state()
            self.assertEqual('up', state)

    def test_bonding_min_links(self):
        # configure member interfaces
        min_links = len(self._interfaces)
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

            self.cli_set(self._base_path + [interface, 'min-links', str(min_links)])

        self.cli_commit()

        # verify config
        for interface in self._interfaces:
            tmp = get_interface_config(interface)

            self.assertEqual(min_links, tmp['linkinfo']['info_data']['min_links'])
            # check LACP default rate
            self.assertEqual('slow',    tmp['linkinfo']['info_data']['ad_lacp_rate'])

    def test_bonding_lacp_rate(self):
        # configure member interfaces
        lacp_rate = 'fast'
        for interface in self._interfaces:
            for option in self._options.get(interface, []):
                self.cli_set(self._base_path + [interface] + option.split())

            self.cli_set(self._base_path + [interface, 'lacp-rate', lacp_rate])

        self.cli_commit()

        # verify config
        for interface in self._interfaces:
            tmp = get_interface_config(interface)

            # check LACP minimum links (default value)
            self.assertEqual(0,         tmp['linkinfo']['info_data']['min_links'])
            self.assertEqual(lacp_rate, tmp['linkinfo']['info_data']['ad_lacp_rate'])

    def test_bonding_hash_policy(self):
        # Define available bonding hash policies
        hash_policies = ['layer2', 'layer2+3', 'layer2+3', 'encap2+3', 'encap3+4']
        for hash_policy in hash_policies:
            for interface in self._interfaces:
                for option in self._options.get(interface, []):
                    self.cli_set(self._base_path + [interface] + option.split())

                self.cli_set(self._base_path + [interface, 'hash-policy', hash_policy])

            self.cli_commit()

            # verify config
            for interface in self._interfaces:
                defined_policy = read_file(f'/sys/class/net/{interface}/bonding/xmit_hash_policy').split()
                self.assertEqual(defined_policy[0], hash_policy)

    def test_bonding_multi_use_member(self):
        # Define available bonding hash policies
        for interface in ['bond10', 'bond20']:
            for member in self._members:
                self.cli_set(self._base_path + [interface, 'member', 'interface', member])

        # check validate() - can not use the same member interfaces multiple times
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(self._base_path + ['bond20'])

        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
