cmake_minimum_required(VERSION 3.8)
project(robocon2027_field)

find_package(ament_cmake REQUIRED)

install(DIRECTORY urdf worlds meshes launch rviz docs
  DESTINATION share/${PROJECT_NAME})

install(PROGRAMS scripts/generate_field.py
  DESTINATION lib/${PROJECT_NAME})

ament_package()
