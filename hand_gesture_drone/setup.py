from setuptools import find_packages, setup

package_name = "hand_gesture_drone"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Abdelfattah",
    maintainer_email="you@example.com",
    description="Hand gesture drone controller — MediaPipe + ROS 2 + PX4",
    license="MIT",
    entry_points={
        "console_scripts": [
            "drone_controller = hand_gesture_drone.drone_controller:main",
        ],
    },
)
