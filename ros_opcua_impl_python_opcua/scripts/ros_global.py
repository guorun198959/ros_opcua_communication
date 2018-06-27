# Rewrote some ros functions need in project
import rosgraph
import roslib
import rosnode
import rospy
import rosmsg
from rosmsg import *

from opcua import ua, Server
from opcua.common.ua_utils import get_nodes_of_namespace

object_id_dict = {'bool': ua.ObjectIds.Boolean,
                  'byte': ua.ObjectIds.Byte,
                  'int': ua.ObjectIds.Int16,
                  'int8': ua.ObjectIds.SByte,
                  'uint8': ua.ObjectIds.Byte,
                  'int16': ua.ObjectIds.Int16,
                  'uint16': ua.ObjectIds.UInt16,
                  'int32': ua.ObjectIds.Int32,
                  'uint32': ua.ObjectIds.UInt32,
                  'int64': ua.ObjectIds.Int64,
                  'uint64': ua.ObjectIds.UInt64,
                  'float': ua.ObjectIds.Float,
                  'float32': ua.ObjectIds.Float,
                  'float64': ua.ObjectIds.Float,
                  'double': ua.ObjectIds.Double,
                  'string': ua.ObjectIds.String,
                  'str': ua.ObjectIds.String,
                  'array': ua.ObjectIds.Enumeration,
                  'Time': ua.ObjectIds.Time,
                  'time': ua.ObjectIds.Time}


# ros messages  'message' --> nodeVariableType
messageExportPath = 'message.xml'
new_messageExportPath = 'new_message.xml'
messageNode = {}

# ros Topics  'topic_name' --> 'topic_node'
topicNode = {}


def get_object_ids(type_name):
    if type_name == 'int16':
        rospy.logwarn('Int16??')
    dv = object_id_dict.get(type_name, None)
    if dv is None:
        rospy.logerr('Can not create type with name ' + type_name)
    return dv


def _get_ros_packages(mode):
    """
    same as the command line 'rosmsg packages'
    :return: ROS messages as a list
    """
    return sorted([x for x in iterate_packages(rospkg.RosPack(), mode)])


def _get_ros_msg(mode):
    ret = []
    if mode == MODE_MSG:
        suffix = 'msg'
    else:
        suffix = 'srv'
    ros_packages = _get_ros_packages(mode)
    for (p, directory) in ros_packages:
        for file_name in getattr(rosmsg, '_list_types')(directory, suffix, mode):
            ret.append(p + '/' + file_name)
    return ret


def get_ros_messages():
    """
    same as the command line 'rosmsg list'
    :return: list of ros package/message pairs
    """
    return _get_ros_msg(MODE_MSG)


def get_ros_services():
    """
    same as the command line 'rossrv list'
    :return: list of ros package/service pairs
    """
    return _get_ros_msg(MODE_SRV)


def get_ros_package(package_name):
    return list_types(package_name, mode=MODE_MSG)


def get_nodes_info(node_name):
    master = rosgraph.Master(node_name)
    state = master.getSystemState()

    nodes = []
    for s in state:
        for t, l in s:
            nodes.extend(l)
    nodes = list(set(nodes))
    nodes_info_dict = {}
    for node in nodes:
        node_info = {'pubs': sorted([t for t, l in state[0] if node in l]),
                     'subs': sorted([t for t, l in state[1] if node in l]),
                     'srvs': sorted([t for t, l in state[2] if node in l])}
        nodes_info_dict[node] = node_info
    return nodes_info_dict


def next_name(hierarchy, index_of_last_processed):
    """
    Returns the hierarchy as one string from the first remaining part on.
    :param hierarchy:
    :param index_of_last_processed:
    :return:
    """
    try:
        output = ''
        counter = index_of_last_processed + 1
        while counter < len(hierarchy):
            output += hierarchy[counter]
            counter += 1
        return output
    except Exception as ex:
        rospy.logerr('Error encountered ', ex)


def rosnode_cleanup():
    _, unpinged = rosnode.rosnode_ping_all()
    if unpinged:
        master = rosgraph.Master(rosnode.ID)
        rosnode.cleanup_master_blacklist(master, unpinged)


def correct_type(node, type_message):
    data_value = node.get_data_value()
    result = node.get_value()
    if isinstance(data_value, ua.DataValue):
        if type_message.__name__ in ('float', 'double'):
            return float(result)
        if type_message.__name__ == 'int':
            return int(result) & 0xff
        if type_message.__name__ in ('Time', 'Duration'):
            return rospy.Time(result)
    else:
        rospy.logerr("can't convert: " + str(node.get_data_value.Value))
        return None


def _get_ros_class(class_type, class_name):
    try:
        if class_type == 'message':
            ros_class = roslib.message.get_message_class(class_name)
        elif class_type == 'service':
            ros_class = roslib.message.get_service_class(class_name)
        else:
            raise rospy.ROSException
        return ros_class()
    except rospy.ROSException:
        rospy.logfatal('Could not create %s, %s class not found!' % (class_name, class_type))
        return None
    except TypeError:
        rospy.logfatal('Could not create %s, %s class not found!' % (class_name, class_type))
        return None


def get_message_class(message):
    return _get_ros_class('message', message)


def get_service_class(service):
    return _get_ros_class('service', service)


class BasicROSServer:
    def __init__(self):
        self.server = Server()

        self.server.set_endpoint('opc.tcp://0.0.0.0:21554/RosServer')
        self.server.set_server_name('ROS UA Server')
        self._idx_name = 'http://ros.org/rosopcua'
        self.idx = self.server.register_namespace(self._idx_name)
        self.ros_node_name = 'rosopcua'
        self.ros_msgs = None

    def __enter__(self):
        rospy.init_node(self.ros_node_name, log_level=rospy.INFO)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.server.stop()
        quit()

    def start_server(self):
        self.server.start()

    def export_messages(self):
        rospy.logwarn(' ----- check if Extension Object fully supported! ------ ')
        rospy.loginfo(' ----- start exporting node message to xml ------ ')
        node_to_export = get_nodes_of_namespace(self.server, [self.idx])
        rospy.loginfo(' ----- %s nodes are to be exported ------ ' % len(node_to_export))
        self.server.export_xml(node_to_export, new_messageExportPath)
        rospy.loginfo(' ----- node message exported to %s ------ ' % new_messageExportPath)

    def get_ros_data_type_id(self, name):
        return self.ros_msgs[name]
