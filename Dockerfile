FROM ubuntu:15.04

MAINTAINER Ben Parham

ENV DEBIAN_FRONTEND=noninteractive

# Add locale and export encoding (necessary for Berkshelf parser)
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8

# Install required packages
RUN apt-get update && apt-get --yes --quiet install \
gcc \
python \
python-dev \
python-virtualenv \
rsync \
ssh

# Install chefDK (chef development kit)
ADD https://opscode-omnibus-packages.s3.amazonaws.com/debian/6/x86_64/chefdk_0.3.6-1_amd64.deb /tmp/chefdk.deb
RUN dpkg -i /tmp/chefdk.deb
RUN rm -rf /tmp/chefdk.deb
RUN chef gem install knife-solo
RUN chef gem install knife-solo_data_bag

# Create work directory
RUN mkdir -p /project/save_deployment
WORKDIR /project/save_deployment

# Create python virtualenv and install required python packages
ADD ./requirements.txt requirements.txt
RUN virtualenv /project/env
RUN echo "source /project/env/bin/activate" > ~/.bashrc
RUN /project/env/bin/pip --quiet install --requirement requirements.txt
