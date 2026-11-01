"""Open the Robocon 2027 field in gz sim (ROS 2 Jazzy / Gazebo Harmonic).

  ros2 launch robocon2027_field gazebo.launch.py
  ros2 launch robocon2027_field gazebo.launch.py gz_args:="-r -s"      # no GUI (server only)
  ros2 launch robocon2027_field gazebo.launch.py objects:=false        # field only, no blocks / Mustika
  ros2 launch robocon2027_field gazebo.launch.py bridge_clock:=false
"""
from launch import LaunchDescription
import os

from ament_index_python.packages import get_package_share_directory
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    world_file = PythonExpression(["'robocon2027.sdf' if '", LaunchConfiguration('objects'),
                                   "'.lower() == 'true' else 'robocon2027_field_only.sdf'"])
    world = PathJoinSubstitution([FindPackageShare('robocon2027_field'), 'worlds', world_file])
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py'])),
        launch_arguments={'gz_args': [LaunchConfiguration('gz_args'), ' ', world]}.items())

    clock_bridge = Node(
        package='ros_gz_bridge', executable='parameter_bridge', name='clock_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen', condition=IfCondition(LaunchConfiguration('bridge_clock')))

    # lets gz sim resolve model://robocon2027_field/meshes/...
    share_parent = os.path.dirname(get_package_share_directory('robocon2027_field'))
    resource_path = AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', share_parent)

    return LaunchDescription([
        resource_path,
        DeclareLaunchArgument('gz_args', default_value='-r',
                              description='extra gz sim arguments (-r = start running, -s = no GUI)'),
        DeclareLaunchArgument('objects', default_value='true',
                              description='true = with Earth Blocks, Sky Blocks and Mustika; false = field only'),
        DeclareLaunchArgument('bridge_clock', default_value='true',
                              description='bridge /clock so use_sim_time:=true works'),
        gz_sim,
        clock_bridge,
    ])
