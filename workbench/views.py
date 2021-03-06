"""Django views implementing the XBlock workbench.

This code is in the Workbench layer.

"""

import logging
import mimetypes
import pkg_resources
from StringIO import StringIO

from django.http import HttpResponse, Http404
from django.shortcuts import render_to_response
from django.views.decorators.csrf import ensure_csrf_cookie

from .runtime import Usage, create_xblock, MEMORY_KVS
from .scenarios import SCENARIOS
from .request import webob_to_django_response, django_to_webob_request


# --- Set up an in-memory logger

LOG_STREAM = None

def setup_logging():
    global LOG_STREAM
    LOG_STREAM = StringIO()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(LOG_STREAM)
    handler.setFormatter(logging.Formatter("<p>%(asctime)s %(name)s %(levelname)s: %(message)s</p>"))
    root_logger.addHandler(handler)

setup_logging()

log = logging.getLogger(__name__)


# We don't really have authentication and multiple students, just accept their
# id on the URL.
def get_student_id(request):
    student_id = int(request.GET.get('student', '1'))
    return student_id


#---- Views -----

def index(request):
    return render_to_response('index.html', {
        'scenarios': [(i, scenario.description) for i, scenario in enumerate(SCENARIOS)]
    })


@ensure_csrf_cookie
def show_scenario(request, scenario_id):
    student_id = get_student_id(request)
    log.info("Start show_scenario %s for %s", scenario_id, student_id)
    scenario = SCENARIOS[int(scenario_id)]
    usage = scenario.usage
    usage.store_initial_state()
    block = create_xblock(usage, "student%s" % student_id)
    frag = block.runtime.render(block, {}, 'student_view')
    log.info("End show_scenario %s", scenario_id)
    return render_to_response('block.html', {
        'scenario': scenario,
        'block': block,
        'body': frag.body_html(),
        'database': MEMORY_KVS,
        'head_html': frag.head_html(),
        'foot_html': frag.foot_html(),
        'log': LOG_STREAM.getvalue(),
        'student_id': student_id,
        'usage': usage,
    })


def handler(request, usage_id, handler_slug):
    student_id = get_student_id(request)
    log.info("Start handler %s/%s for %s", usage_id, handler_slug, student_id)
    usage = Usage.find_usage(usage_id)
    block = create_xblock(usage, "student%s" % student_id)
    request = django_to_webob_request(request)
    request.path_info_pop()
    request.path_info_pop()
    result = block.runtime.handle(block, handler_slug, request)
    log.info("End handler %s/%s", usage_id, handler_slug)
    return webob_to_django_response(result)


def package_resource(request, package, resource):
    if ".." in resource:
        raise Http404
    try:
        content = pkg_resources.resource_string(package, "static/" + resource)
    except IOError:
        raise Http404
    mimetype, _ = mimetypes.guess_type(resource)
    return HttpResponse(content, mimetype=mimetype)
