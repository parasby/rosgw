if command -v docker &> /dev/null
then
  docker run --name ros2gw_c -u root --rm -it -p 9001:9000 ros2gw
  exit
elif command -v podman &> /dev/null
then
  podman run --name ros2gw_c -u root --rm -it -p 9001:9000 ros2gw
  exit
else
  echo cannot find docker or podman
fi
