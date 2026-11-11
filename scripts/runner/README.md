# Remote execution runner

This directory builds `aios-runner:latest`, the restricted execution image used by the optional SSH executor.

The image runs as an unprivileged user, uses `/workspace` as its working directory, and installs common runtimes (Python, Node.js, Git, and curl). At runtime the AIOS executor adds Docker limits, a read-only root filesystem, a temporary `/tmp`, no network, a process limit, and a timeout.

Build locally:

```bash
docker build -t aios-runner:latest scripts/runner
```

Test locally:

```bash
docker run --rm --network none --read-only --tmpfs /tmp:rw,size=64m aios-runner:latest 'echo AIOS_OK'
```

The user-server bootstrap builds this image locally if it is absent. It does not fetch an unpublished image name from a registry.

Review `Dockerfile` before building. For production use, pin the base image by digest and maintain a security update process.
