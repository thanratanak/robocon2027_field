"""Show the Robocon 2027 field in RViz2.

  ros2 launch robocon2027_field rviz.launch.py
  ros2 launch robocon2027_field rviz.launch.py with_objects:=true   # also blocks + Mustika at start positions

The field is published as a RobotModel on /field/robot_description (so it does not clash with your
robot's own /robot_description) and attached to the TF frame "map" (origin = field centre,
+x toward Blue, +y toward the Mustika Pillar). Your robot's TF tree should hang under "map".
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context, *args, **kwargs):
    share = get_package_share_directory('robocon2027_field')
    with_objects = LaunchConfiguration('with_objects').perform(context).lower() == 'true'
    urdf = os.path.join(share, 'urdf', 'field_with_objects.urdf' if with_objects else 'field.urdf')
    with open(urdf, 'r') as fh:
        description = fh.read()
    use_sim_time = LaunchConfiguration('use_sim_time').perform(context).lower() == 'true'

    rsp = Node(
        package='robot_state_publisher', executable='robot_state_publisher',
        namespace='field', name='field_state_publisher', output='screen',
        parameters=[{'robot_description': description, 'use_sim_time': use_sim_time}],
        remappings=[('/tf', '/tf'), ('/tf_static', '/tf_static')])

    static_tf = Node(
        package='tf2_ros', executable='static_transform_publisher', name='map_to_field',
        arguments=['--x', '0', '--y', '0', '--z', '0', '--roll', '0', '--pitch', '0', '--yaw', '0',
                   '--frame-id', 'map', '--child-frame-id', 'field'],
        parameters=[{'use_sim_time': use_sim_time}])

    rviz = Node(
        package='rviz2', executable='rviz2', name='rviz2', output='screen',
        arguments=['-d', os.path.join(share, 'rviz', 'field.rviz')],
        parameters=[{'use_sim_time': use_sim_time}])

    nodes = [rsp, static_tf]
    if LaunchConfiguration('rviz').perform(context).lower() == 'true':
        nodes.append(rviz)
    return nodes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('with_objects', default_value='false',
                              description='also draw Earth Blocks, Sky Blocks and the Mustika (start positions only)'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='true', description='start RViz2 (false = only publish the field)'),
        OpaqueFunction(function=_setup),
    ])
