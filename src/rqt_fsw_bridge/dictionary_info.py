#!/usr/bin/env python

# Copyright (c) 2011, Dorian Scholz, TU Darmstadt
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above
#     copyright notice, this list of conditions and the following
#     disclaimer in the documentation and/or other materials provided
#     with the distribution.
#   * Neither the name of the TU Darmstadt nor the names of its
#     contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Determining bandwidth is not supported right now
# See: https://github.com/ros2/ros2cli/issues/132
# And: https://github.com/ros2/rclpy/pull/242
# from io import StringIO

from python_qt_binding.QtCore import qWarning
# from ros2topic.verb.hz import ROSTopicHz
from rqt_py_common.message_helpers import get_message_class

from ament_index_python.packages import get_package_share_directory

from fsw_ros2_bridge_msgs.msg import MessageInfo

from rosidl_runtime_py import get_message_interfaces
import importlib
from os import walk
import json


class DictionaryInfo:
    def __init__(self, node):
        self._node = node
        self._message_info_list = []
        self._msg_dict = {"commands": [], "telemetry": [], "helper": []}

    def set_message_info(self, plugin_pkg, pkg_name, message_info_list):
        self._message_info_list = message_info_list
        return self.get_message_dict()

    def get_message_dict(self):
        for m in self._message_info_list:
            if m.msg_type is MessageInfo.TELEMETRY:
                self._msg_dict["telemetry"].append(m.msg_name)
            elif m.msg_type is MessageInfo.COMMAND:
                self._msg_dict["commands"].append(m.msg_name)
            else:
                self._msg_dict["helper"].append(m.msg_name)
        self._node.get_logger().info("Message Dictionary:")
        self._node.get_logger().info("  found " + str(len(self._msg_dict["commands"])) + " command msgs")
        self._node.get_logger().info("  found " + str(len(self._msg_dict["telemetry"])) + " telemetry msgs")
        self._node.get_logger().info("  found " + str(len(self._msg_dict["helper"])) + " helper msgs")

        return self._msg_dict

    def get_msg_type(self, msg_name):
        if msg_name in self._msg_dict["telemetry"]: return "TELEMETRY"
        if msg_name in self._msg_dict["commands"]: return "COMMAND"
        if msg_name in self._msg_dict["helper"]: return "HELPER"
        return "UNKNOWN"


    # def build_msg_dict(self, plugin_pkg, pkg_name):
    #     for package_name, message_names in get_message_interfaces().items():
    #         for message_name in message_names:
    #                 m = f'{package_name}/{message_name}'
    #                 # self.get_logger().info("found msg type: " + m + ", pkg: " + package_name + ", msg: " + message_name)            
    #                 message_name = message_name.replace("msg/", "")
    #                 if package_name == pkg_name:
    #                     MsgType = getattr(importlib.import_module(package_name + ".msg"), message_name)
    #                     d = MsgType.get_fields_and_field_types()
    #                     if 'cmd_id' in d.keys():
    #                         self._msg_dict["commands"].append(message_name)
    #                     elif 'Tlm' in message_name:
    #                         self._msg_dict["telemetry"].append(message_name)
    #                     else:
    #                         self._msg_dict["helper"].append(message_name)

    #     self.load_message_dictionary(plugin_pkg)
    #     return self._msg_dict

    def get_msg_struct(self, pkg_name, msg_name):
        for package_name, message_names in get_message_interfaces().items():
            for message_name in message_names:
                    m = f'{package_name}/{message_name}'
                    # self.get_logger().info("found msg type: " + m + ", pkg: " + package_name + ", msg: " + message_name)            
                    message_name = message_name.replace("msg/", "")
                    if (message_name == msg_name) and (package_name == pkg_name):
                        MsgType = getattr(importlib.import_module(package_name + ".msg"), message_name)
                        return MsgType.get_fields_and_field_types()
        return {}


    def load_message_dictionary(self, plugin_pkg):
        pkg_resource_dir = get_package_share_directory(plugin_pkg)
        msg_resource_dir = pkg_resource_dir + "/config/message_dictionary.json"
        # print("pkg_resource_dir: " + pkg_resource_dir)
        # print("msg_resource_dir: " + msg_resource_dir)
        # msg_info_files = next(walk(msg_resource_dir), (None, None, []))[2]  # [] if no file

        # print("found msg files:\n" + str(msg_info_files))

        #     with open('json_data.json') as json_file:
        # data = json.load(json_file)
        # print(data)


    def save_message_info(self, plugin_pkg, msg_name, info):
        pkg_resource_dir = get_package_share_directory(plugin_pkg)
        msg_resource_dir = pkg_resource_dir + "/dict"
        msg_file_name = msg_resource_dir + "/" + msg_name + ".json"
        # print("writing msg info file: " + msg_file_name)

        msg_dict = {}
        msg_dict["name"] = msg_name
        msg_dict["pkg_name"] = plugin_pkg
        msg_dict["info"] = info
        with open(msg_file_name, 'w') as json_file:
            json.dump(msg_dict, json_file)

    def load_message_info(self, plugin_pkg, msg_name):
        pkg_resource_dir = get_package_share_directory(plugin_pkg)
        msg_resource_dir = pkg_resource_dir + "/dict"
        msg_file_name = msg_resource_dir + "/" + msg_name + ".json"
        print("============== reading msg info file: " + msg_file_name)

        info = {}
        try:
            with open(msg_file_name, 'r') as f:
                info = json.load(f)
                # print(" " + str(info))
        except FileNotFoundError:
            print(msg_file_name + ": file not found")
            return None
        return info