pip download \
    bcrypt==4.1.2 \
    cffi==1.17.1 \
    greenlet==3.2.4 \
    httptools==0.6.4 \
    MarkupSafe==3.0.2 \
    numpy==2.3.3 \
    pandas==2.3.2 \
    psycopg2-binary==2.9.9 \
    pydantic-core==2.20.1 \
    PyYAML==6.0.2 \
    SQLAlchemy==2.0.36 \
    watchfiles==1.1.0 \
    websockets==15.0.1 \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    --python-version 3.12 \
    -d ./packages
