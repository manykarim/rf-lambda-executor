FROM public.ecr.aws/lambda/python

RUN curl -sL https://rpm.nodesource.com/setup_16.x | bash -
RUN yum install -y nodejs dbus-glib alsa-lib mesa-libgbm xrandr gtkspell3 cups-libs at-spi2-atk && yum clean all
COPY requirements.txt ./
RUN python3.9 -m pip install -r requirements.txt -t . && python3.9 -m Browser.entry init
COPY app.py ./
CMD ["app.lambda_handler"]