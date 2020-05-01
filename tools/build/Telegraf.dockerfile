FROM golang:1.11-alpine as builder

ARG BUILD_BRANCH=develop

RUN apk --update upgrade && \
    apk add git make curl dep

RUN go get 'github.com/kontaktio/telegraf'

RUN mv $GOPATH/src/github.com/kontaktio $GOPATH/src/github.com/influxdata
WORKDIR $GOPATH/src/github.com/influxdata/telegraf
RUN git checkout "${BUILD_BRANCH}"
RUN dep ensure -vendor-only
RUN make go-install

FROM alpine:3.11
COPY --from=builder /go/bin/* /usr/bin/

RUN apk update
RUN apk add
RUN apk --update upgrade && \
    apk add --no-cache python py-pip ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/cache/apk/* && \
    wget -O /etc/ssl/ca-bundle.pem https://curl.haxx.se/ca/cacert.pem

RUN pip install --no-cache awscli

COPY tools/build/start_telegraf_and_acceptor.sh /start_telegraf_and_acceptor.sh
RUN chmod +x /start_telegraf_and_acceptor.sh

RUN mkdir /root/.aws

EXPOSE 8080

ENV CONFIG_FROM_S3="true"
ENV TELEGRAF_CONFIG_PATH="/etc/telegraf/telegraf.conf"

ENTRYPOINT "/start_telegraf_and_acceptor.sh"