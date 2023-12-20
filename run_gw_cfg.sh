if command -v docker &> /dev/null
then
  docker run --name ros2gw_1 -u root --rm -it -v ${PWD}/example/cfg:/opt/gateway/cfg ros2gw file:=/opt/gateway/cfg/example_cfg.json
  exit
elif command -v podman &> /dev/null
then
  podman run --name ros2gw_1 -u root --rm -it -v ${PWD}/example/cfg:/opt/gateway/cfg ros2gw file:=/opt/gateway/cfg/example_cfg.json
  exit
else
  echo cannot find docker or podman
fi
