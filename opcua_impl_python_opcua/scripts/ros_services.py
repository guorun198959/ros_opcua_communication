#!/usr/bin/env python

# Thanks to:
# https://github.com/ros-visualization/rqt_common_plugins/blob/groovy-devel/rqt_service_caller/src/rqt_service_caller/service_caller_widget.py
import math
import numpy
import random
import time

import genpy
import rospy
import rosservice
from opcua import ua


class OpcUaROSService:
    def __init__(self, server, parent, idx, service_name, service_class):
        self.server = server
        self.name = service_name
        self._class = service_class
        self.proxy = rospy.ServiceProxy(self.name, self._class)
        self.counter = 0
        self._nodes = {}
        self.expressions = {}
        self._eval_locals = {}

        for module in (math, random, time):
            self._eval_locals.update(module.__dict__)
        self._eval_locals['genpy'] = genpy
        del self._eval_locals['__name__']
        del self._eval_locals['__doc__']
        # Build the Array of inputs
        sample_req = self._class._request_class()
        sample_resp = self._class._response_class()
        inputs = getargarray(sample_req)
        outputs = getargarray(sample_resp)

        parent.add_method(idx, self.name, self.call_service, [ua.VariantType.Int64], [ua.VariantType.Boolean])

    def call_service(self, parent, inputs):
        print ("reached callback")
        request = self._class._request_class()
        # print (request)
        # self.fill_message_slots(request, self.name, self.expressions, self.counter)
        try:
            print("executing ros call")
            #  response = self.proxy(request)
            # return response
            return[ua.Variant(True, ua.VariantType.Boolean)]
        except Exception as e:
            print(e)

    def fill_message_slots(self, message, topic_name, expressions, counter):
        try:
            print("Filling message slots!")

            if not hasattr(message, '__slots__'):
                print("message has no slots")
                return
            else:
                print(message.__slots__)
                for slot_name in message.__slots__:
                    slot_key = topic_name + '/' + slot_name
                    print ("filling slot " + slot_name)
                    # if no expression exists for this slot_key, continue with it's child slots
                    if slot_key not in expressions:
                        self.fill_message_slots(getattr(message, slot_name), slot_key, expressions, counter)
                        continue

                    expression = expressions[slot_key]
                    if len(expression) == 0:
                        continue

                    # get slot type
                    slot = getattr(message, slot_name)
                    if hasattr(slot, '_type'):
                        slot_type = slot._type
                    else:
                        slot_type = type(slot)

                    self._eval_locals['i'] = counter
                    value = self._evaluate_expression(expression, slot_type)
                    if value is not None:
                        setattr(message, slot_name, value)
                    print(message)
                print (message)
        except Exception as e:
            print(e)

    def _evaluate_expression(self, expression, slot_type):
        successful_eval = True
        successful_conversion = True

        try:
            # try to evaluate expression
            value = eval(expression, {}, self._eval_locals)
        except Exception:
            # just use expression-string as value
            value = expression
            successful_eval = False

        try:
            # try to convert value to right type
            value = slot_type(value)
        except Exception:
            successful_conversion = False

        if successful_conversion:
            return value
        elif successful_eval:
            print ("fill_message_slots(): can not convert expression to slot type: %s -> %s' % (type(value), slot_type)")
        else:
            print('fill_message_slots(): failed to evaluate expression: %s' % expression)

        return None

    def recursive_delete_items(self, item):
        for child in item.get_children():
            self.recursive_delete_items(child)
            if child in self._nodes:
                del self._nodes[child]
            self.server.delete_nodes([child])
        self.server.delete_nodes([item])


def primitivetovariant(typeofprimitive):
    if isinstance(typeofprimitive, list):
        dv = ua.VariantType.Null
    elif typeofprimitive == bool:
        dv = ua.VariantType.Boolean
    elif typeofprimitive == numpy.byte:
        dv = ua.VariantType.Byte
    elif typeofprimitive == int:
        dv = ua.VariantType.Int32
    elif typeofprimitive == float:
        dv = ua.VariantType.Float
    elif typeofprimitive == numpy.double:
        dv = ua.VariantType.Double
    elif typeofprimitive == str:
        dv = ua.VariantType.String
    else:
        # print (typeofprimitive)
        return ua.VariantType.ByteString
    return dv


def getargarray(sample_req):
    array = []
    counter = 0
    for slot_name in sample_req.__slots__:
        print ("current slot name: ")
        print (slot_name)
        slot = getattr(sample_req, slot_name)
        print("current slot: ")
        print (slot)
        if hasattr(slot, '_type'):
            slot_type = slot._type
            slot_desc = slot._description
            input_arg = ua.Argument()
            input_arg.Name = "Input Argument " + repr(counter)
            input_arg.DataType = ua.NodeId(getobjectidfromtype(type))
            input_arg.ValueRank = -1
            input_arg.ArrayDimensions = []
            input_arg.Description = ua.LocalizedText("primitive")
        else:
            slot_type = primitivetovariant(type(slot))
            input_arg = slot_type
        array.append(input_arg)
        counter += 1

    return array


def refresh_services(server, servicesDict, idx, services_object_opc):
    rosservices = rosservice.get_service_list(include_nodes=False)

    for service_name_ros in rosservices:
        try:
            if service_name_ros not in servicesDict or servicesDict[service_name_ros] is None:
                service = OpcUaROSService(server, services_object_opc, idx, service_name_ros,
                                          rosservice.get_service_class_by_name(service_name_ros))
                servicesDict[service_name_ros] = service
        except (rosservice.ROSServiceException, rosservice.ROSServiceIOException) as e:
            server.stop()
            print (e)

    rosservices = rosservice.get_service_list(include_nodes=False)
    for service_nameOPC in servicesDict:
        found = False
        for rosservice_name in rosservices:
            if service_nameOPC == rosservice_name:
                found = True
        if not found and servicesDict[service_nameOPC] is not None:
            servicesDict[service_nameOPC].recursive_delete_items(server.get_node(ua.NodeId(service_nameOPC, idx)))
            servicesDict[service_nameOPC] = None


def getobjectidfromtype(type_name):
    if type_name == 'bool':
        dv = ua.ObjectIds.Boolean
    elif type_name == 'byte':
        dv = ua.ObjectIds.Byte
    elif type_name == 'int8':
        dv = ua.ObjectIds.SByte
    elif type_name == 'uint8':
        dv = ua.ObjectIds.Byte
    elif type_name == 'int16':
        dv = ua.ObjectIds.Int16
    elif type_name == 'uint16':
        dv = ua.ObjectIds.UInt16
    elif type_name == 'int32':
        dv = ua.ObjectIds.Int32
    elif type_name == 'uint32':
        dv = ua.ObjectIds.UInt32
    elif type_name == 'int64':
        dv = ua.ObjectIds.Int64
    elif type_name == 'uint64':
        dv = ua.ObjectIds.UInt64
    elif type_name == 'float' or type_name == 'float32' or type_name == 'float64':
        dv = ua.ObjectIds.Float
    elif type_name == 'double':
        dv = ua.ObjectIds.Double
    elif type_name == 'string':
        dv = ua.ObjectIds.String
    else:
        # print (type_name)
        return None
    return dv

# def main(args):
#     global server
#
#     rospy.init_node("opcua_server")
#     servicesDict = {}
#     server = Server()
#     server.set_endpoint("opc.tcp://0.0.0.0:21554/")
#     server.set_server_name("ROS ua Server")
#
#     server.start()  # setup our own namespace, this is expected
#     uri = "http://ros.org"
#     idx = server.register_namespace(uri)
#
#     # get Objects node, this is where we should put our custom stuff
#     objects = server.get_objects_node()
#
#     servicesopc = objects.add_object(idx, "ROS-Services")
#
#     while True:
#         refresh_services(servicesDict, idx, servicesopc)
#         time.sleep(2)
#     rospy.spin()
#
#
# if __name__ == "__main__":
#     main(sys.argv)