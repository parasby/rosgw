# ROS-Gateway(rosgw): Enhancing ROS Availability across Multiple Network Environments

## Features

  * Support for rosbridge v2 protocol.
  * ROS topic forwarding: Forward ROS topics from internal network to other networks.
  * ROS Topic Reverse Forwarding: Allows ROS topics from other networks to be forwarded to the internal network.
  * Expose ROS Services: Make ROS services on the internal network available to other networks.
  * Reserve ROS Services: Make ROS services exposed on other networks available on the internal network.
  * Expose ROS Actions: Make ROS actions exposed on the internal network available to other networks.
  * Reserve ROS Actions: Make ROS actions exposed on other networks available on the internal nNetwork.
  * Supports conversion from ROS to REST API and from REST API to ROS data.
  * Inspired by [ros2-web-bridge](https://github.com/RobotWebTools/ros2-web-bridge)
  
## Install and Run

### Run under Docker

1. Clone and make docker container
  ```bash
  $ git clone https://github.com/lge-cloud-ai-robot/rosgw.git
  $ cd rosgw
  $ build_gw.sh 
    or
  $ docker build --rm -t ros2gw ./src
  ```
2. Run the gateway container
  ```bash
  $ run_gw_center.sh
    or 
  $ docker run --name ros2gw_c -u root --rm -d -p 9001:9000 ros2gw
  ```
3. Check the gatway working

- Open http://localhost:9001/docs with a web browser

4. Run the gateway with example config file
  ```bash
  $ run_gw_cfg.sh
    or
  $ docker run --name ros2gw_1 -u root --rm -it -v ${PWD}/example/cfg:/opt/gateway/cfg ros2gw file:=/opt/gateway/cfg/example_cfg.json
  ```


5. Appendix : example config file ./example/cfg/example_cfg.json
  ```
  [
      {
          "title":"jackal1",
          "active": true,
          "address": "ws://172.28.165.227:9001",   <--target gateway service address and port (websocket)
          "publish": [     
              {"name":"/kitti/camera_color_left/image_raw",    <--local topics to forward to other gateway
                "messageType":"sensor_msgs/msg/Image",
                "compression":"cbor-raw"
              }
          ],
          "subscribe": [
              {"name":"/cmd_vel", "messageType":"geometry_msgs/msg/Twist"}  <-- remote topics to receive from other gateway
          ]
      }
  ]
  ``` 
