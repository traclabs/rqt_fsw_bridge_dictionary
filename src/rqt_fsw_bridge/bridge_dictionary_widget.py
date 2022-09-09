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

from __future__ import division

import itertools
import os

import rclpy

from PyQt5 import QtCore, QtGui, QtWidgets

from ament_index_python import get_resource
from python_qt_binding import loadUi
from python_qt_binding.QtCore import Qt, QTimer, qWarning, Slot
from python_qt_binding.QtGui import QIcon
from python_qt_binding.QtWidgets import QHeaderView, QMenu, QTreeWidgetItem, QWidget
from rqt_py_common.message_helpers import get_message_class

from fsw_ros2_bridge_msgs.srv import GetMessageInfo
from fsw_ros2_bridge_msgs.srv import GetPluginInfo
from fsw_ros2_bridge_msgs.msg import MessageInfo

from .bridge_dictionary_info import BridgeDictionaryInfo


class BridgeDictionaryWidget(QWidget):
    """
    main class inherits from the ui window class.

    You can specify the topics that the topic pane.

    BridgeDictionaryWidget.start must be called in order to update topic pane.
    """

    SELECT_BY_NAME = 0
    SELECT_BY_MSGTYPE = 1

    DEFAULT_TOPIC_TIMEOUT_SECONDS = 10.0

    # _column_names = ['topic', 'type', 'bandwidth', 'rate', 'value', '_msg_order']
    _column_names = ['structure', 'type']

    def __init__(self, node, plugin=None, selected_topics=None,
                 select_topic_type=SELECT_BY_NAME, topic_timeout=DEFAULT_TOPIC_TIMEOUT_SECONDS):
        """
        Initialize the BridgeDictionaryWidget class.

        @type selected_topics: list of tuples.
        @param selected_topics: [($NAME_TOPIC$, $TYPE_TOPIC$), ...]
        @type select_topic_type: int
        @param select_topic_type: Can specify either the name of topics or by
                                  the type of topic, to filter the topics to
                                  show. If 'select_topic_type' argument is
                                  None, this arg shouldn't be meaningful.
        """
        super(BridgeDictionaryWidget, self).__init__()

        self._node = node
        self._logger = self._node.get_logger().get_child('rqt_fsw_bridge.BridgeDictionaryWidget')
        self._select_topic_type = select_topic_type
        self._topic_timeout = topic_timeout
        self._connected_to_bridge = False

        _, package_path = get_resource('packages', 'rqt_fsw_bridge')
        ui_file = os.path.join(package_path, 'share', 'rqt_fsw_bridge',
                               'resource', 'BridgeDictionaryWidget.ui')
        loadUi(ui_file, self)
        self._plugin = plugin
        # self.msg_tree_widget.sortByColumn(
        #     self._column_names.index('_msg_order'), Qt.AscendingOrder)
        # header = self.msg_tree_widget.header()
        # try:
        #     setSectionResizeMode = header.setSectionResizeMode  # Qt5
        # except AttributeError:
        #     setSectionResizeMode = header.setResizeMode  # Qt4
        # setSectionResizeMode(QHeaderView.ResizeToContents)
        # header.customContextMenuRequested.connect(
        #     self.handle_header_view_customContextMenuRequested)
        # header.setContextMenuPolicy(Qt.CustomContextMenu)


        # self.pkg_name = ""
        # self.msg_pkg_combo_box.addItems([self.pkg_name])

        self._plugin_info = None
        self._msg_dict = {}

        self.bridge_dictionary_info = BridgeDictionaryInfo(self._node, None, None)

        # self.msg_dict = self.bridge_dictionary_info.get_pkg_message_info(self.pkg_name)
        # self._build_dictionary_tree(self.msg_dict)


        # Whether to get all topics or only the topics that are set in advance.
        # Can be also set by the setter method "set_selected_topics".
        # self._selected_topics = selected_topics

        # self._current_topic_list = []
        # self._topics = {}
        # self._tree_items = {}
        self._column_index = {}
        for column_name in self._column_names:
            self._column_index[column_name] = len(self._column_index)
        # self.msg_tree_widget.setColumnHidden(self._column_index['_msg_order'], True)

        
        self.bridge_plugin_info_client = self._node.create_client(GetPluginInfo, '/fsw_ros2_bridge/get_plugin_info')
        self.bridge_message_info_client = self._node.create_client(GetMessageInfo, '/fsw_ros2_bridge/get_message_info')

        self.refresh_plugin_info()

        # # init and start update timer
        self._timer_refresh_topics = QTimer(self)
        self._timer_refresh_topics.timeout.connect(self.refresh_plugin_info)

    def set_topic_specifier(self, specifier):
        self._select_topic_type = specifier

    def start(self):
        """Call this method to start updating the topic pane."""
        self._timer_refresh_topics.start(1000)

    def send_plugin_info_request(self):
        req = GetPluginInfo.Request()
        future = self.bridge_plugin_info_client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future)
        return future.result()

    def send_message_info_request(self, pkg_name):
        req = GetMessageInfo.Request()
        req.pkg_name = pkg_name
        future = self.bridge_message_info_client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future)
        return future.result()

    @Slot()
    def refresh_plugin_info(self):

        if not self._connected_to_bridge:
    
            self._node.get_logger().info("trying to get plugin info")

            if self.bridge_plugin_info_client.wait_for_service(timeout_sec=1.0):
                self._plugin_info = self.send_plugin_info_request()
                self._pkg_name = self._plugin_info.msg_pkg
                self._node.get_logger().info("setting msg pkg: " + self._pkg_name)

                self.pkg_name = ""
                self.msg_pkg_label.setText(self.pkg_name)

                if self.bridge_message_info_client.wait_for_service(timeout_sec=1.0):
                    r = self.send_message_info_request(self._plugin_info.msg_pkg)
                    
                    self._node.get_logger().info("setting msg info with: " + str(len(r.msg_info)))

                    self._msg_dict = {"commands": [], "telemetry": [], "helper": []}
                    for m in r.msg_info:
                        if m.msg_type is MessageInfo.TELEMETRY:
                            self._msg_dict["telemetry"].append(m.msg_name)
                        elif m.msg_type is MessageInfo.COMMAND:
                            self._msg_dict["commands"].append(m.msg_name)
                        else:
                            self._msg_dict["helper"].append(m.msg_name)

                    self._node.get_logger().info("  found " + str(len(self._msg_dict["commands"])) + " command msgs")
                    self._node.get_logger().info("  found " + str(len(self._msg_dict["telemetry"])) + " telemetry msgs")
                    self._node.get_logger().info("  found " + str(len(self._msg_dict["helper"])) + " helper msgs")
                    
                    self._build_dictionary_tree(self._msg_dict)
                    self.msg_tree_widget.itemClicked.connect(self.on_msg_item_clicked)

        
            self._connected_to_bridge = True
        

        """Refresh tree view items."""
        # if self._selected_topics is None:
        #     topic_list = self._node.get_topic_names_and_types()
        #     if topic_list is None:
        #         self._logger.error(
        #             'Not even a single published topic found. Check network configuration')
        #         return
        # else:  # Topics to show are specified.
        #     topic_list = self._selected_topics
        #     topic_specifiers_server_all = None
        #     topic_specifiers_required = None

        #     self._logger.debug('refresh_topics) self._selected_topics=%s' % (topic_list, ))

        #     if self._select_topic_type == self.SELECT_BY_NAME:
        #         topic_specifiers_server_all = \
        #             [name for name, types in self._node.get_topic_names_and_types()]
        #         topic_specifiers_required = {name for name, types in topic_list}
        #     elif self._select_topic_type == self.SELECT_BY_MSGTYPE:
        #         # The topics that are required (by whoever uses this class).
        #         all_topic_types = [types for name, types in topic_list]

        #         topic_specifiers_required = set(itertools.chain.from_iterable(all_topic_types))

        #         # The required topics that match with published topics.
        #         topics_match = \
        #             [(name, types) for name, types in self._node.get_topic_names_and_types()
        #                 if (set(types) & topic_specifiers_required)]
        #         topic_list = topics_match
        #         self._logger.debug('selected & published topic types=%s' % (topic_list, ))

        #     self._logger.debug('server_all=%s\nrequired=%s\ntlist=%s' % (
        #         topic_specifiers_server_all, topic_specifiers_required, topic_list))
        #     if len(topic_list) == 0:
        #         self._logger.error(
        #             'None of the following required topics are found.\n(NAME, TYPE): %s' %
        #             (self._selected_topics, ))
        #         return

        # if self._current_topic_list != topic_list:
        #     self._current_topic_list = topic_list

        #     # start new topic dict
        #     new_topics = {}

        #     for topic_name, topic_types in topic_list:
        #         # if topic is new or has changed its type
        #         if topic_name not in self._topics or \
        #                 self._topics[topic_name]['type'] != topic_types[0]:
        #             # create new BridgeDictionaryInfo
        #             if len(topic_types) > 1:
        #                 qWarning('rqt_fsw_bridge: Topic "' + topic_name +
        #                          '" has more than one type, choosing the first one of type ' +
        #                          topic_types[0])
        #             bridge_dictionary_info = BridgeDictionaryInfo(self._node, topic_name, topic_types[0])
        #             message_instance = None
        #             if bridge_dictionary_info.message_class is not None:
        #                 message_instance = bridge_dictionary_info.message_class()
        #             # add it to the dict and tree view
        #             topic_item = self._recursive_create_widget_items(
        #                 self.msg_tree_widget, topic_name, topic_types, message_instance)
        #             new_topics[topic_name] = {
        #                 'item': topic_item,
        #                 'info': bridge_dictionary_info,
        #                 'type': topic_types[0],
        #             }
        #         else:
        #             # if topic has been seen before, copy it to new dict and
        #             # remove it from the old one
        #             new_topics[topic_name] = self._topics[topic_name]
        #             del self._topics[topic_name]

        #     # clean up old topics
        #     for topic_name in list(self._topics.keys()):
        #         self._topics[topic_name]['info'].stop_monitoring()
        #         index = self.msg_tree_widget.indexOfTopLevelItem(
        #             self._topics[topic_name]['item'])
        #         self.msg_tree_widget.takeTopLevelItem(index)
        #         del self._topics[topic_name]

        #     # switch to new topic dict
        #     self._topics = new_topics

        # self._update_topics_data()

    def _update_topics_data(self):
        pass
        # for topic in self._topics.values():
        #     bridge_dictionary_info = topic['info']
        #     if bridge_dictionary_info.monitoring:
        #         # If ROSTopicHz.get_hz is called too frequently, it may return None because it does
        #         # not have valid statistics
        #         rate = None
        #         hz_result = bridge_dictionary_info.get_hz(bridge_dictionary_info._topic_name)
        #         if hz_result is None:
        #             last_valid_time = bridge_dictionary_info.get_last_printed_tn(bridge_dictionary_info._topic_name)
        #             current_rostime = bridge_dictionary_info._clock.now().nanoseconds
        #             if last_valid_time + self._topic_timeout * 1e9 > current_rostime:
        #                 # If the last time this was valid was less than the topic timeout param
        #                 # then ignore it
        #                 return
        #         else:
        #             rate, _, _, _, _ = hz_result
        #             rate *= 1e9
        #         rate_text = '%1.2f' % rate if rate is not None else 'unknown'

        #         # update bandwidth
        #         # TODO (brawner) Currently unsupported
        #         bandwidth_text = 'unknown'
        #         # bytes_per_s, _, _, _ = bridge_dictionary_info.get_bw()
        #         # if bytes_per_s is None:
        #         #     bandwidth_text = 'unknown'
        #         # elif bytes_per_s < 1000:
        #         #     bandwidth_text = '%.2fB/s' % bytes_per_s
        #         # elif bytes_per_s < 1000000:
        #         #     bandwidth_text = '%.2fKB/s' % (bytes_per_s / 1000.)
        #         # else:
        #         #     bandwidth_text = '%.2fMB/s' % (bytes_per_s / 1000000.)

        #         # update values
        #         value_text = ''
        #         self.update_value(bridge_dictionary_info._topic_name, bridge_dictionary_info.last_message)

        #     else:
        #         rate_text = ''
        #         # bytes_per_s = None
        #         bandwidth_text = ''
        #         value_text = 'not monitored' if bridge_dictionary_info.error is None else bridge_dictionary_info.error

        #     self._tree_items[bridge_dictionary_info._topic_name].setText(self._column_index['rate'],
        #                                                       rate_text)
        #     # self._tree_items[bridge_dictionary_info._topic_name].setData(
        #     #    self._column_index['bandwidth'], Qt.UserRole, bytes_per_s)
        #     self._tree_items[bridge_dictionary_info._topic_name].setText(
        #         self._column_index['bandwidth'], bandwidth_text)
        #     self._tree_items[bridge_dictionary_info._topic_name].setText(
        #         self._column_index['value'], value_text)

    def update_value(self, topic_name, message):
        pass
        # if hasattr(message, 'get_fields_and_field_types'):
        #     for slot_name in message.get_fields_and_field_types().keys():
        #         self.update_value(topic_name + '/' + slot_name, getattr(message, slot_name))

        # elif type(message) in (list, tuple) and \
        #         (len(message) > 0) and \
        #         hasattr(message[0], '__slots__'):

        #     for index, slot in enumerate(message):
        #         if topic_name + '[%d]' % index in self._tree_items:
        #             self.update_value(topic_name + '[%d]' % index, slot)
        #         else:
        #             base_type_str, _ = self._extract_array_info(
        #                 self._tree_items[topic_name].text(self._column_index['type']))
        #             i = self._recursive_create_widget_items(
        #                 self._tree_items[topic_name],
        #                 topic_name + '[%d]' % index, [base_type_str], slot)
        #             i.setText(self._column_index['_msg_order'], str(index))
        #     # remove obsolete children
        #     if len(message) < self._tree_items[topic_name].childCount():
        #         for i in range(len(message), self._tree_items[topic_name].childCount()):
        #             item_topic_name = topic_name + '[%d]' % i
        #             self._recursive_delete_widget_items(self._tree_items[item_topic_name])
        # else:
        #     if topic_name in self._tree_items:
        #         self._tree_items[topic_name].setText(self._column_index['value'], repr(message))
        #         self._tree_items[topic_name].setData(self._column_index['value'],
        #                                              Qt.UserRole, message)

    def _extract_array_info(self, type_str):
        pass
        # array_size = None
        # if '[' in type_str and type_str[-1] == ']':
        #     type_str, array_size_str = type_str.split('[', 1)
        #     array_size_str = array_size_str[:-1]
        #     if len(array_size_str) > 0:
        #         array_size = int(array_size_str)
        #     else:
        #         array_size = 0
        # elif type_str.startswith('sequence<') and type_str.endswith('>'):
        #     type_str = type_str[9:-1]

        # return type_str, array_size

    # def _recursive_create_widget_items(self, parent, topic_name, type_names, message):
    #     if parent is self.msg_tree_widget:
    #         # show full topic name with preceding namespace on toplevel item
    #         topic_text = topic_name
    #         item = TreeWidgetItem(self._toggle_monitoring, topic_name, parent)
    #     else:
    #         topic_text = topic_name.split('/')[-1]
    #         if '[' in topic_text:
    #             topic_text = topic_text[topic_text.index('['):]
    #         item = TreeWidgetItem2(parent)
    #     item.setText(self._column_index['topic'], topic_text)
    #     item.setText(self._column_index['type'], ', '.join(type_names))
    #     item.setData(0, Qt.UserRole, topic_name)
    #     self._tree_items[topic_name] = item
    #     if hasattr(message, 'get_fields_and_field_types'):
    #         fields_and_field_types = message.get_fields_and_field_types()
    #         for index, slot_name in enumerate(fields_and_field_types.keys()):
    #             type_name = fields_and_field_types[slot_name]
    #             i = self._recursive_create_widget_items(
    #                 item, topic_name + '/' + slot_name, [type_name], getattr(message, slot_name))
    #             i.setText(self._column_index['_msg_order'], str(index))

    #     elif not type_names:
    #         base_type_str, array_size = self._extract_array_info(type_names[0])
    #         try:
    #             base_instance = get_message_class(base_type_str)()
    #         except (ValueError, TypeError):
    #             base_instance = None
    #         if array_size is not None and hasattr(base_instance, '__slots__'):
    #             for index in range(array_size):
    #                 i = self._recursive_create_widget_items(
    #                     item, topic_name + '[%d]' % index, base_type_str, base_instance)
    #                 i.setText(self._column_index['_msg_order'], str(index))
    #     return item

    # def _toggle_monitoring(self, topic_name):
    #     item = self._tree_items[topic_name]
    #     if item.checkState(0):
    #         self._topics[topic_name]['info'].start_monitoring()
    #     else:
    #         self._topics[topic_name]['info'].stop_monitoring()

    # def _recursive_delete_widget_items(self, item):
    #     def _recursive_remove_items_from_tree(item):
    #         for index in reversed(range(item.childCount())):
    #             _recursive_remove_items_from_tree(item.child(index))
    #         topic_name = item.data(0, Qt.UserRole)
    #         del self._tree_items[topic_name]
    #     _recursive_remove_items_from_tree(item)
    #     item.parent().removeChild(item)

    # @Slot('QPoint')
    # def handle_header_view_customContextMenuRequested(self, pos):
    #     header = self.msg_tree_widget.header()

    #     # show context menu
    #     menu = QMenu(self)
    #     action_toggle_auto_resize = menu.addAction('Toggle Auto-Resize')
    #     action_restore_message_order = None
    #     if self.msg_tree_widget.sortColumn() not in (-1, self._column_index['_msg_order']):
    #         action_restore_message_order = menu.addAction('Restore message order')
    #     action = menu.exec_(header.mapToGlobal(pos))

    #     # evaluate user action
    #     if action is action_toggle_auto_resize:
    #         try:
    #             sectionResizeMode = header.sectionResizeMode  # Qt5
    #             setSectionResizeMode = header.setSectionResizeMode  # Qt5
    #         except AttributeError:
    #             sectionResizeMode = header.resizeMode  # Qt4
    #             setSectionResizeMode = header.setResizeMode  # Qt4
    #         if sectionResizeMode(0) == QHeaderView.ResizeToContents:
    #             setSectionResizeMode(QHeaderView.Interactive)
    #         else:
    #             setSectionResizeMode(QHeaderView.ResizeToContents)
    #     if action is action_restore_message_order:
    #         self.msg_tree_widget.sortByColumn(
    #             self._column_index['_msg_order'], Qt.AscendingOrder)

    # @Slot('QPoint')
    # def on_msg_tree_widget_customContextMenuRequested(self, pos):
    #     item = self.msg_tree_widget.itemAt(pos)
    #     if item is None:
    #         return

    #     # show context menu
    #     menu = QMenu(self)
    #     action_item_expand = menu.addAction(QIcon.fromTheme('zoom-in'), 'Expand All Children')
    #     action_item_collapse = menu.addAction(QIcon.fromTheme('zoom-out'), 'Collapse All Children')
    #     action = menu.exec_(self.msg_tree_widget.mapToGlobal(pos))

    #     # evaluate user action
    #     if action in (action_item_expand, action_item_collapse):
    #         expanded = (action is action_item_expand)

    #         def recursive_set_expanded(item):
    #             item.setExpanded(expanded)
    #             for index in range(item.childCount()):
    #                 recursive_set_expanded(item.child(index))
    #         recursive_set_expanded(item)

    def shutdown_plugin(self):
        # for topic in self._topics.values():
        #     topic['info'].stop_monitoring()
        self._timer_refresh_topics.stop()

    # def set_selected_topics(self, selected_topics):
    #     """
    #     Set selected topics.

    #     @param selected_topics: list of tuple. [(topic_name, topic_type)]
    #     @type selected_topics: []
    #     """
    #     self._logger.debug('set_selected_topics topics={}'.format(len(selected_topics)))
    #     self._selected_topics = selected_topics

    # TODO(Enhancement) Save/Restore tree expansion state
    def save_settings(self, plugin_settings, instance_settings):
        header_state = self.msg_tree_widget.header().saveState()
        instance_settings.set_value('tree_widget_header_state', header_state)

    def restore_settings(self, pluggin_settings, instance_settings):
        if instance_settings.contains('tree_widget_header_state'):
            header_state = instance_settings.value('tree_widget_header_state')
            if not self.msg_tree_widget.header().restoreState(header_state):
                self._logger.warn('rqt_fsw_bridge: Failed to restore header state.')


    def _is_primitive(self, t):
        return t in ["int8", "int16", "int32", "uint8", "uint16", "uint32", "float8", "float16", "float32", "bool", "string"]


    def _build_dictionary_tree(self, data):
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


    def _build_msg_struct_tree(self, data, par=None):
        items = []
        for key, values in data.items():
            if par is None:
                item = QTreeWidgetItem([key])
            else:
                item = QTreeWidgetItem([key, par])

            item.setText(self._column_index['structure'], key)
            item.setText(self._column_index['type'], values)

            if not self._is_primitive(data[key]):
                [pkg_name, msg_type] = data[key].split("/")
                m = self.bridge_dictionary_info.get_msg_struct(pkg_name, msg_type)
                child = self._build_msg_struct_tree(m, data[key])
                item.addChild(child)
            items.append(item)
        
        if par is None:
            self.msg_struct_tree.insertTopLevelItems(0, items)

        return item
    

        

    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, int)
    def on_msg_item_clicked(self, it, col):
        self.msg_struct_tree.clear()
        for t in self._msg_dict["commands"]:
            if t == it.text(col):
                info_str = "This is info about COMMAND msg: " + t
                self.msg_info_text.setText(info_str)
                s = self.bridge_dictionary_info.get_msg_struct(self._pkg_name, t)
                self._build_msg_struct_tree(s) 
        for t in self._msg_dict["telemetry"]:
            if t == it.text(col):
                info_str = "This is info about TELEMETRY msg: " + t
                self.msg_info_text.setText(info_str)
                s = self.bridge_dictionary_info.get_msg_struct(self._pkg_name, t)
                self._build_msg_struct_tree(s) 
        for t in self._msg_dict["helper"]:
            if t == it.text(col):
                info_str = "This is info about HELPER msg: " + t
                self.msg_info_text.setText(info_str)
                s = self.bridge_dictionary_info.get_msg_struct(self._pkg_name, t)
                self._build_msg_struct_tree(s) 

        self.msg_struct_tree.resizeColumnToContents(0)
        return


# class TreeWidgetItem(QTreeWidgetItem):

#     def __init__(self, check_state_changed_callback, topic_name, parent=None):
#         super(TreeWidgetItem, self).__init__(parent)
#         self._check_state_changed_callback = check_state_changed_callback
#         self._topic_name = topic_name
#         self.setCheckState(0, Qt.Unchecked)

#     def setData(self, column, role, value):
#         if role == Qt.CheckStateRole:
#             state = self.checkState(column)
#         super(TreeWidgetItem, self).setData(column, role, value)
#         if role == Qt.CheckStateRole and state != self.checkState(column):
#             self._check_state_changed_callback(self._topic_name)

#     def __lt__(self, other_item):
#         column = self.treeWidget().sortColumn()
#         if column == BridgeDictionaryWidget._column_names.index('bandwidth'):
#             return self.data(column, Qt.UserRole) < other_item.data(column, Qt.UserRole)
#         return super(TreeWidgetItem, self).__lt__(other_item)


# class TreeWidgetItem2(QTreeWidgetItem):

#     def __init__(self, parent=None):
#         super(TreeWidgetItem2, self).__init__(parent)

#     def __lt__(self, other_item):
#         column = self.treeWidget().sortColumn()
#         if column == BridgeDictionaryWidget._column_names.index('value'):
#             # use non-string values if comparable
#             lhs = self.data(column, Qt.UserRole)
#             rhs = other_item.data(column, Qt.UserRole)
#             try:
#                 return lhs < rhs
#             except TypeError:
#                 pass
#         return super(TreeWidgetItem2, self).__lt__(other_item)

