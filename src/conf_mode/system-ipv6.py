#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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

from sys import exit
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import leaf_node_changed
from vyos.util import call
from vyos.util import dict_search
from vyos.util import sysctl_write
from vyos.util import write_file
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'ipv6']

    opt = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    tmp = leaf_node_changed(conf, base + ['disable'])
    if tmp: opt['reboot_required'] = {}

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    opt = dict_merge(default_values, opt)

    return opt

def verify(opt):
    pass

def generate(opt):
    pass

def apply(opt):
    # disable IPv6 globally
    tmp = dict_search('disable', opt)
    value = '1' if (tmp != None) else '0'
    sysctl_write('net.ipv6.conf.all.disable_ipv6', value)

    if 'reboot_required' in opt:
        print('Changing IPv6 disable parameter will only take affect\n' \
              'when the system is rebooted.')

    # configure multipath
    tmp = dict_search('multipath.layer4_hashing', opt)
    value = '1' if (tmp != None) else '0'
    sysctl_write('net.ipv6.fib_multipath_hash_policy', value)

    # Apply ND threshold values
    # table_size has a default value - thus the key always exists
    size = int(dict_search('neighbor.table_size', opt))
    # Amount upon reaching which the records begin to be cleared immediately
    sysctl_write('net.ipv6.neigh.default.gc_thresh3', size)
    # Amount after which the records begin to be cleaned after 5 seconds
    sysctl_write('net.ipv6.neigh.default.gc_thresh2', size // 2)
    # Minimum number of stored records is indicated which is not cleared
    sysctl_write('net.ipv6.neigh.default.gc_thresh1', size // 8)

    # enable/disable IPv6 forwarding
    tmp = dict_search('disable_forwarding', opt)
    value = '0' if (tmp != None) else '1'
    write_file('/proc/sys/net/ipv6/conf/all/forwarding', value)

    # configure IPv6 strict-dad
    tmp = dict_search('strict_dad', opt)
    value = '2' if (tmp != None) else '1'
    for root, dirs, files in os.walk('/proc/sys/net/ipv6/conf'):
        for name in files:
            if name == 'accept_dad':
                write_file(os.path.join(root, name), value)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
