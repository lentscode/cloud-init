FROM ubuntu:24.04

ENV container=docker

# cloud-init runs its normal systemd stages against the NoCloud seed mounted by
# run-docker-cloud-init.sh at /var/lib/cloud/seed/nocloud.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      cloud-init dbus lsb-release systemd systemd-sysv sudo \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && printf '%s\n' \
      'datasource_list: [ NoCloud, None ]' \
      > /etc/cloud/cloud.cfg.d/99-docker-nocloud.cfg

STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
