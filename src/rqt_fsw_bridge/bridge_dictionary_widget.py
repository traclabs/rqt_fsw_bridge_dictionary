#!/usr/bin/env python3

from __future__ import division
import os

from python_qt_binding import loadUi
from python_qt_binding.QtCore import Qt, QTimer, Slot
from python_qt_binding.QtWidgets import QWidget, QTreeWidgetItem, QTableWidgetItem
from PyQt5 import QtCore, QtGui, QtWidgets

import rclpy
from ament_index_python import get_resource

from fsw_ros2_bridge_msgs.srv import GetMessageInfo, SetMessageInfo, GetPluginInfo
from fsw_ros2_bridge_msgs.msg import MessageInfo

from .dictionary_info import DictionaryInfo


class BridgeDictionaryWidget(QWidget):

    _column_names = ['structure', 'type']

    def __init__(self, node, plugin):
        super(BridgeDictionaryWidget, self).__init__()

        self._node = node
        self._plugin = plugin
        self._logger = self._node.get_logger().get_child('rqt_fsw_bridge.BridgeDictionaryWidget')
        self._connected_to_bridge = False
        self._msg_pkg_name = ""
        self._plugin_pkg_name = ""
        self._plugin_name = ""

        # set up UI
        _, package_path = get_resource('packages', 'rqt_fsw_bridge')
        ui_file = os.path.join(package_path, 'share', 'rqt_fsw_bridge', 'resource', 'BridgeDictionaryWidget.ui')
        loadUi(ui_file, self)
        self.setup_ui_connections()

        # necessary?
        self._column_index = {}
        for column_name in self._column_names:
            self._column_index[column_name] = len(self._column_index)

        # bridge info
        self._plugin_info = None
        self._msg_dict = {}
        self._dictionary_info = DictionaryInfo(self._node)

        # ros clients
        self.bridge_plugin_info_client = self._node.create_client(GetPluginInfo, '/fsw_ros2_bridge/get_plugin_info')
        self.bridge_get_message_info_client = self._node.create_client(GetMessageInfo, '/fsw_ros2_bridge/get_message_info')
        self.bridge_set_message_info_client = self._node.create_client(SetMessageInfo, '/fsw_ros2_bridge/set_message_info')

        # connection timer
        # self.wait_for_plugin()
        self._timer_wait_for_bridge = QTimer(self)
        self._timer_wait_for_bridge.timeout.connect(self.wait_for_plugin)

    def start(self):
        self._timer_wait_for_bridge.start(1000)

    def shutdown_plugin(self):
        self._timer_wait_for_bridge.stop()
   
    def save_settings(self, plugin_settings, instance_settings):
        header_state = self.msg_tree_widget.header().saveState()
        instance_settings.set_value('tree_widget_header_state', header_state)

    def restore_settings(self, pluggin_settings, instance_settings):
        if instance_settings.contains('tree_widget_header_state'):
            header_state = instance_settings.value('tree_widget_header_state')
            if not self.msg_tree_widget.header().restoreState(header_state):
                self._logger.warn('rqt_fsw_bridge: Failed to restore header state.')

    def setup_ui_connections(self):
        self.msg_tree_widget.itemClicked.connect(self._on_msg_item_clicked)
        self.clear_info_button.clicked.connect(self.clear_info_pressed)
        self.save_info_button.clicked.connect(self.save_info_pressed)
        self.reload_info_button.clicked.connect(self.reload_info_pressed)

    def send_plugin_info_request(self):
        req = GetPluginInfo.Request()
        future = self.bridge_plugin_info_client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future)
        return future.result()

    def send_message_info_request(self, pkg_name):
        req = GetMessageInfo.Request()
        req.pkg_name = pkg_name
        future = self.bridge_get_message_info_client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future)
        return future.result()

    @Slot()
    def wait_for_plugin(self):
        if (not self._connected_to_bridge) and (not self._msg_dict):
            self._node.get_logger().info("Trying to connect to FSW bridge...")
            if self.bridge_plugin_info_client.wait_for_service(timeout_sec=1.0):
                if self._plugin_info is None:
                    self._plugin_info = self.send_plugin_info_request()
                    self._plugin_name = self._plugin_info.plugin_name
                    self._plugin_pkg_name = self._plugin_name.split('.')[0]
                    self._msg_pkg_name = self._plugin_info.msg_pkg

                    self._node.get_logger().info("setting plugin: " + self._plugin_name)
                    self._node.get_logger().info("setting plugin pkg: " + self._plugin_pkg_name)
                    self._node.get_logger().info("setting msg pkg: " + self._msg_pkg_name)

                    self.msg_pkg_label.setText(self._msg_pkg_name)
                    self.plugin_name_label.setText(self._plugin_name)

            if self._plugin_info is not None:
                if self.bridge_get_message_info_client.wait_for_service(timeout_sec=1.0):
                    r = self.send_message_info_request(self._plugin_info.msg_pkg)
                    if r:
                        self._connected_to_bridge = True
                        self._node.get_logger().info("setting msg info with: " + str(len(r.msg_info)))
                        self._msg_dict = self._dictionary_info.set_message_info(self._plugin_pkg_name, self._msg_pkg_name, r.msg_info)
                        if self._msg_dict:
                            self.build_dictionary_tree(self._msg_dict) 

    def is_primitive(self, t):
        return t in ["int8", "int16", "int32", "uint8", "uint16", "uint32", "float8", "float16", "float32", "bool", "string"]

    def build_dictionary_tree(self, data):
        items = []
        for key, values in data.items():
            item = QTreeWidgetItem([key])
            for value in values:
                ext = value.split(".")[-1].upper()
                child = QTreeWidgetItem([value, ext])
                item.addChild(child)
            items.append(item)

        self.msg_tree_widget.clear()
        self.msg_tree_widget.insertTopLevelItems(0, items)

    def build_msg_struct_tree(self, data, par=None):
        items = []
        item = None
        for key, values in data.items():
            if par is None:
                item = QTreeWidgetItem([key])
            else:
                item = QTreeWidgetItem([key, par])

            item.setText(self._column_index['structure'], key)
            item.setText(self._column_index['type'], values)

            if not self.is_primitive(data[key]):
                [pkg_name, msg_type] = data[key].split("/")
                m = self._dictionary_info.get_msg_struct(pkg_name, msg_type)
                child = self.build_msg_struct_tree(m, data[key])
                item.addChild(child)
            items.append(item)
        
        if par is None:
            self.msg_struct_tree.insertTopLevelItems(0, items)

        return item

    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, int)
    def _on_msg_item_clicked(self, it, col):
        self.msg_struct_tree.clear()

        msg_name = ""
        stored_info = None

        t = it.text(col)
        if any(t in sublist for sublist in self._msg_dict.values()):
            msg_name = t

        stored_info = self._dictionary_info.load_message_info(self._plugin_pkg_name, msg_name)
        if stored_info is None:
            info_str = "This is info about " + self._dictionary_info.get_msg_type(msg_name) + " msg: " + msg_name
            self.msg_info_text.setText(info_str)
        else:
            self.msg_info_text.setText(stored_info["info"])

        s = self._dictionary_info.get_msg_struct(self._msg_pkg_name, msg_name)
        self.build_msg_struct_tree(s) 

        msg_name_item = QTableWidgetItem()
        msg_name_item.setText(msg_name)
        self.msg_table_header.setItem(0,0, msg_name_item)

        msg_pkg_name_item = QTableWidgetItem()
        msg_pkg_name_item.setText(self._msg_pkg_name)
        self.msg_table_header.setItem(1,0, msg_pkg_name_item)

        msg_type_item = QTableWidgetItem()
        msg_type_item.setText(self._dictionary_info.get_msg_type(msg_name))
        self.msg_table_header.setItem(2,0, msg_type_item)

        self.msg_struct_tree.resizeColumnToContents(0)
        return

    @QtCore.pyqtSlot()
    def clear_info_pressed(self):
        self._node.get_logger().info("clear info button")
        item = self.msg_tree_widget.currentItem().text(0)
        self._node.get_logger().info(" item: " + str(item))
        info_str = "This is info about " + self._dictionary_info.get_msg_type(item) + " msg: " + str(item) 
        self.msg_info_text.setText(info_str)
        return

    @QtCore.pyqtSlot()
    def save_info_pressed(self):
        self._node.get_logger().info("save info button")
        item = self.msg_tree_widget.currentItem().text(0)
        self._node.get_logger().info(" item: " + str(item))
        info = self.msg_info_text.toPlainText()
        self._dictionary_info.save_message_info(self._plugin_pkg_name, str(item), info)
        return

    @QtCore.pyqtSlot()
    def reload_info_pressed(self):
        self._node.get_logger().info("reload info button")
        item = self.msg_tree_widget.currentItem().text(0)
        self._node.get_logger().info(" item: " + str(item))
        stored_info = self._dictionary_info.load_message_info(self._plugin_pkg_name, str(item))
        if stored_info is None:
            info_str = "This is info about " + self._dictionary_info.get_msg_type(item) + " msg: " + str(item) 
            self.msg_info_text.setText(info_str)
        else:
            self.msg_info_text.setText(stored_info["info"])
        return
