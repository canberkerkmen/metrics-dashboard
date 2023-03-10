from flask import Flask, render_template, request, jsonify

import pymongo
from flask_pymongo import PyMongo


from jaeger_client import Config
from jaeger_client.metrics.prometheus import PrometheusMetricsFactory
from flask_opentracing import FlaskTracing
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)

app.config["MONGO_DBNAME"] = "example-mongodb"
app.config[
    "MONGO_URI"
] = "mongodb://example-mongodb-svc.default.svc.cluster.local:27017/example-mongodb"

mongo = PyMongo(app)

metrics = PrometheusMetrics(app)
metrics.info("app_info", "App Info", version="1.0.3")
common_counter = metrics.counter(
    'by_endpoint_counter', 'Request count by endpoints',
    labels={'endpoint': lambda: request.endpoint}
)

record_requests_by_status = metrics.summary(
    'requests_by_status', 'Request latencies by status',
    labels={'status': lambda: request.status_code()}
)

def init_tracer(service):

    config = Config(
        config={
            "sampler": {"type": "const", "param": 1},
            "logging": True,
            "reporter_batch_size": 1,
        },
        service_name=service,
        validate=True,
        metrics_factory=PrometheusMetricsFactory(service_name_label=service),
    )

    # this call also sets opentracing.tracer
    return config.initialize_tracer()

jaeger_tracer = init_tracer("backend")
tracing = FlaskTracing(jaeger_tracer, True, app)

@app.route('/')
def homepage():
    with jaeger_tracer.start_span('hello world') as span:
        hw = "Hello World"
        span.set_tag('message', "Hello World")
    return "Hello World"

@app.route('/api')
def my_api():
    with jaeger_tracer.start_span('api') as span:
        answer = "something"
        span.set_tag('message', answer)
        return jsonify(repsonse=answer)

@app.route("/star", methods=["POST"])
def add_star():
    star = mongo.db.stars
    name = request.json["name"]
    distance = request.json["distance"]
    star_id = star.insert({"name": name, "distance": distance})
    new_star = star.find_one({"_id": star_id})
    output = {"name": new_star["name"], "distance": new_star["distance"]}
    return jsonify({"result": output})

@app.route("/error")
@metrics.summary('requests_by_status_5xx', 'Status Code', labels={
    'code': lambda r: '500'
})
def oops():
    return ":(", 500
# register additional default metrics
metrics.register_default(
    metrics.counter(
        'by_path_counter', 'Request count by request paths',
        labels={'path': lambda: request.path}
    )
)

if __name__ == "__main__":
    app.run()
