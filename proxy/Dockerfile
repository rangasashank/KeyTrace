FROM golang:1.24-bookworm AS build
WORKDIR /app
COPY go.* ./
RUN go mod download
COPY . .
RUN go test -mod=readonly ./... && CGO_ENABLED=0 go build -o /proxy .
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /proxy /proxy
CMD ["/proxy"]
