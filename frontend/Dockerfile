FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY templates/ /usr/share/nginx/html/
COPY static/ /usr/share/nginx/html/static/

EXPOSE 80
