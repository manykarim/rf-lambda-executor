FROM public.ecr.aws/lambda/python:3.9

RUN curl -sL https://rpm.nodesource.com/setup_16.x | bash -
RUN yum install -y nodejs

COPY requirements.txt ./

RUN python3.9 -m pip install -r requirements.txt -t .
RUN python3.9 -m Browser.entry init
# Install playwright dependencies
#RUN yum install -y cups-libs dbus-glib libXrandr libXcursor libXinerama cairo cairo-gobject pango libatk-1.0.so.0 libatk-bridge-2.0.so.0 libxkbcommon.so.0 libXcomposite.so.1 libXdamage.so.1 libXfixes.so.3 libXrandr.so.2 libgbm.so.1 libgtk-3.so.0 libgdk-3.so.0 libpango-1.0.so.0 libcairo.so.2 libatspi.so.0 libxshmfence.so.1 libappindicator-gtk3 liberation-fonts alsa-lib-devel
RUN yum install -y dbus-glib alsa-lib mesa-libgbm xrandr gtkspell3 cups-libs at-spi2-atk
COPY app.py ./
COPY SelectEveryXthTest.py ./
CMD ["app.lambda_handler"]