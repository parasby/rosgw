if command -v docker &> /dev/null
then
  docker build --rm -t ros2gw ./src
  exit
elif command -v podman &> /dev/null
then
  podman build --rm -t ros2gw ./src
  exit
else
  echo cannot find docker or podman
fi
