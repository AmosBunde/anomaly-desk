# Operator console image.
#
# A30 delivers the React queue and detail views. Until then this serves a static page that
# reports what the stack is and which plan item fills it in, so the port contract in
# README.md section 15 is real from M0 and the health check has something to check.

FROM nginx:1.27-alpine

COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80
