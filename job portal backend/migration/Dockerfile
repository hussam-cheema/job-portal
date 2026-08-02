FROM postgres:16-alpine

RUN apk add --no-cache aws-cli

COPY migrate-postgres.sh /usr/local/bin/migrate-postgres
RUN chmod 0755 /usr/local/bin/migrate-postgres

ENTRYPOINT ["/usr/local/bin/migrate-postgres"]
