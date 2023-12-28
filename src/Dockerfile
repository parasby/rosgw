# ROS2 Gateway Docker
#
#
#
FROM ros:foxy-ros-base as ros2_base

ENV DEBIAN_FRONTEND=noninteractive
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp

RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 4B63CF8FDE49746E98FA01DDAD19BAB3CBF125EA
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        python3-pip \
        python-is-python3 \
    && apt-get autoclean -y \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

FROM ros2_base as builder
COPY . /home/user/works
WORKDIR /home/user/works/dist
RUN pip install -r requirements.txt
RUN /bin/bash -c ". /opt/ros/${ROS_DISTRO}/setup.bash; ./build.sh"

FROM ros2_base as runner
WORKDIR /opt/gateway
COPY --from=builder /home/user/works/dist/install ./
COPY --from=builder /home/user/works/dist/requirements.txt ./
COPY --from=builder /home/user/works/entrypoint.sh ./
RUN pip install -r requirements.txt
ENTRYPOINT ["/opt/gateway/entrypoint.sh"]
