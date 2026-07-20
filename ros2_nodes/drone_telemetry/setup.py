from setuptools import setup, find_packages

package_name = 'drone_telemetry'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Edson Carlos',
    maintainer_email='edsoncarlosdevops@gmail.com',
    description='Drone telemetry nodes for ROS 2',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'drone_telemetry_pub = drone_telemetry.drone_telemetry_pub:main',
            'drone_telemetry_sub = drone_telemetry.drone_telemetry_sub:main',
            'waypoint_planner = drone_telemetry.waypoint_planner:main',
        ],
    },
)
