#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function message {
  echo -e "${GREEN}\n---> $1${NC}"
}

function error {
  echo -e "${RED}ERROR: $1${NC}"
}

BUILD=0

function usage {
  echo -e $1
  echo -e "Usage: ./doit"
  echo "Options:"
  echo -e "\t-b -> Build docker image before running"
}

while getopts ":bh" o; do
    case "${o}" in
        b)
          BUILD=1 ;;
        h)
          usage ;;
        \?)
          echo "Invalid option: -$OPTARG"
          usage ;;
    esac
done

# Check docker package is installed
dpkg -s lxc-docker &> /dev/null
if [ $? -ne 0 ]; then
  # echo -e "${RED}Docker not installed. Try apt-get install lxc-docker${NC}"
  error "Docker not installed"
  echo "Try apt-get install lxc-docker"
  exit $?
fi

# Build docker image
if [ $BUILD -eq 1 ]; then
  message "Building docker image..."
  docker build -t save_deployment .
  if [ $? -ne 0 ]; then
    error "Failed to build docker image"
    exit $?
  fi
fi

# Run docker image
message "Running docker image..."
clear
docker run --env-file=deploy/environment -tiv $(pwd):/project/save_deployment save_deployment /bin/bash
