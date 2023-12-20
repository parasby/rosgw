if command -v docker &> /dev/null
then
  docker run --name ros2gw_1 -u root --rm -it -p 9001:9000 ros2gw loglevel:=debug
  exit
elif command -v podman &> /dev/null
then
  podman run --name ros2gw_1 -u root --rm -it -p 9001:9000 ros2gw loglevel:=debug
  exit
else
  echo cannot find docker or podman
fi
