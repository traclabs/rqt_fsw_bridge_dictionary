from setuptools import setup

package_name = 'rqt_fsw_bridge_dictionary'
setup(
    name=package_name,
    version='1.0.0',
    package_dir={'': 'src'},
    packages=[package_name],
    data_files=[
        ('share/' + package_name, ['package.xml']),
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name + '/resource', ['resource/BridgeDictionaryWidget.ui']),
        ('share/' + package_name, ['plugin.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    author='Stephen Hart',
    maintainer='Stephen Hart, Tod Milam',
    maintainer_email='swhart@traclabs.com',
    keywords=['ROS'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Topic :: Software Development',
    ],
    description=(
        'rqt_fsw_bridge_dictionary provides a GUI plugin for displaying information about the FSW ROS2 bridge dictionary'
    ),
    license='BSD',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'rqt_fsw_bridge_dictionary = ' + package_name + '.main:main',
        ],
    },
)
