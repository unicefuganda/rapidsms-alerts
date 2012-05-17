from alerts import Alert
from alerts.models import Notification, NotificationComment, NotificationType
from django.contrib.auth.models import User
from rapidsms.contrib.locations.models import Location
from rapidsms.models import Contact
from datetime import datetime, timedelta
#from cvs.utils import total_attribute_value
from uganda_common.utils import total_attribute_value
from rapidsms_xforms.models import XFormSubmission, XFormSubmissionValue
from healthmodels.models.HealthProvider import HealthProvider

def alerttest(request):
    """
    Example method for adding alerts to your application. This one
    just returns a single empty alert.
    """
    return [Alert('intruder alert! intruder alert!', 'http://google.com')]

def notiftest1():
    for i in range(3):
        notif = Notification(alert_type='alerts._prototyping.TestAlertType')
        notif.uid = 'notif-%d' % i
        notif.text = 'This is alert %d' % i
        notif.url = 'http://google.com'
        yield notif

def notiftest2():
    for i in range(2, 5):
        notif = Notification(alert_type='alerts._prototyping.TestAlertType')
        notif.uid = 'notif-%d' % i
        notif.text = 'This is alert %d' % i
        yield notif

class TestAlertType(NotificationType):
    escalation_levels = ['district', 'moh']

    def users_for_escalation_level(self, esc_level):
        if esc_level == 'district':
            #all users with reporting_district = district
            return [User.objects.get(username='sam')]
        elif esc_level == 'moh':
            #all users with group 'moh'
            return [User.objects.get(username='admin')]

    def auto_escalation_interval(self, esc_level):
        return timedelta(minutes=2) #days=14)

    def escalation_level_name(self, esc_level):
        return {
            'district': 'district team',
            'moh': 'ministry of health',
            }[esc_level]

def mk_notifiable_disease_alert(disease, alert_type, reporting_period, val, loc):
    notif = Notification(alert_type=alert_type)
    notif.uid = 'disease_%s_%s_%s' % (disease, reporting_period, loc.code)
    notif.text = '%d cases of %s reported in %s %s' % (val, disease, loc.name, loc.type.name)
    notif.url = None
    notif.originating_location = loc
    return notif

def notifiable_disease_test(request):
    METRICS = {
        'malaria': {
            'threshold': 3,
            'slug': 'cases_ma',
            'gen': mk_notifiable_disease_alert,
        }
    }
    REPORTING_INTERVAL = 'weekly'

    timestamp = datetime.now()
    if REPORTING_INTERVAL == 'weekly':
        yr, wk, dow = timestamp.isocalendar()
        reporting_period = '%dw%02d' % (yr, wk)
        #period_start = timestamp.date() - timedelta(days=dow - 1)
        #period_end = period_start + timedelta(days=6)
        period_start = datetime(2012, 1, 1)
        period_end = timestamp
        print period_start, period_end
    else:
        raise Exception('unsupported reporting interval [%s]' % REPORTING_INTERVAL)

    for metric, info in METRICS.iteritems():
        #todo: is the end date inclusive or exclusive?
        data = total_attribute_value(info['slug'], period_start, period_end, Location.objects.get(name='Uganda'))
        for total in data:
            loc = Location.objects.get(id=total['location_id'])
            val = total['value']

            if val > info['threshold']:
                # trigger alert
                yield info['gen'](metric, 'alerts._prototyping.NotifiableDiseaseThresholdAlert', reporting_period, val, loc)

# this should serve as the template for most front-line alerts
class NotifiableDiseaseThresholdAlert(NotificationType):
    escalation_levels = ['district', 'moh']

    def users_for_escalation_level(self, esc_level):
        if esc_level == 'district':
            #all users with reporting_district = district
            return [c.user for c in Contact.objects.filter(reporting_location=self.originating_location) if c.user]
        elif esc_level == 'moh':
            #all users with group 'moh'
            return [User.objects.get(username='admin')] #todo: is there an moh 'group'?

    def auto_escalation_interval(self, esc_level):
        return timedelta(minutes=5) #days=14)

    def escalation_level_name(self, esc_level):
        return {
            'district': 'district team',
            'moh': 'ministry of health',
            }[esc_level]
    def sms_users(self):
        hps = HealthProvider.objects.exclude(reporting_location=None, connection=None).filter(groups__name__in=['DHT']).\
        filter(reporting_location__type='district', reporting_location__name=self.originating_location.name)
        return hps

def get_facility_cases_notification(metric, info, debug=False):
    reporting_range = (datetime(2011, 1, 1), datetime.now())
    res = {}
    subs = XFormSubmissionValue.objects.filter(submission__has_errors=False,
            submission__created__range=reporting_range, value_int__gt=info['threshold'],
            ).filter(attribute__slug=info['slug'])
    for sub in subs:
        if not sub.submission.connection or not sub.submission.connection.contact:
            continue
        if not sub.submission.connection.contact.healthproviderbase.healthprovider.facility:
            continue
        facility = sub.submission.connection.contact.healthproviderbase.healthprovider.facility
        loc = sub.submission.connection.contact.reporting_location
        if loc.type.name == 'district':
            district = loc
        else:
            district = loc.get_ancestors().filter(type__slug='district')[0]
        val = sub.value_int
        if district.pk  not in res:
            if debug:
                res[district.pk] = {'name':district.name, 'data':{facility.id:{'name':facility.name, 'type':facility.type.name, 'val':val, 'submission':sub.submission.pk}}}
            else:
                reporter = '%s(%s)' % (sub.submission.connection.contact.name, sub.submission.connection.identity)
                res[district.pk] = {'name':district.name, 'data':{facility.id:{'name':facility.name, 'type':facility.type.name, 'val':val, 'reporters':[reporter]}}}
        else:
            if facility.id not in res[district.pk]['data']:
                if debug:
                    res[district.pk]['data'] = {facility.id:{'name':facility.name, 'type':facility.type.name, 'val':val, 'submission':sub.submission.pk}}
                else:
                    reporter = '%s(%s)' % (sub.submission.connection.contact.name, sub.submission.connection.identity)
                    res[district.pk]['data'] = {facility.id:{'name':facility.name, 'type':facility.type.name , 'val':val, 'reporters':[reporter] }}
            else:
                res[district.pk]['data'][facility.id]['val'] += val
                reporter = '%s(%s)' % (sub.submission.connection.contact.name, sub.submission.connection.identity)
                if not (res[district.pk]['data'][facility.id]['reporters'].__contains__(reporter)):
                    res[district.pk]['data'][facility.id]['reporters'].append(reporter)
    return res

def mk_notifiable_disease_alert2(disease, alert_type, reporting_period, loc, district_data):
    notif = Notification(alert_type=alert_type)
    rr = "%s_%s" % (reporting_period[0].date().strftime('%F'), reporting_period[0].strftime('%H:%M-') + reporting_period[1].strftime('%H:%M'))
    notif.uid = 'disease_%s_%s_%s' % (disease, rr, loc.code)
    txt = "Urgent - "
    has_cases = False
    for d in district_data['data'].values():
        if d['val'] > 0:
            has_cases = True
            txt += "%s at %s %s reported %s cases of %s" % (','.join(d['reporters']), d['name'], d['type'], d['val'], disease)
    if has_cases:
        notif.text = txt
        notif.sms_text = txt
    else: notif.text = ''
    notif.url = None
    notif.originating_location = loc
    return notif

def notifiable_disease_test2():
    METRICS = {
        'malaria': {
            'threshold': 3,
            'slug': 'cases_ma',
            'gen': mk_notifiable_disease_alert2,
        }
    }
    #reporting_period = (datetime.now() - datetime.timedelta(minutes=15), datetime.now())
    reporting_period = (datetime(2011, 1, 1, 0, 0, 0), datetime.now())
    for metric, info in METRICS.iteritems():
        #todo: is the end date inclusive or exclusive?
        data = get_facility_cases_notification(metric, info, False)
        for key in data.keys():
            loc = Location.objects.get(id=key)
            district_data = data[key]
            yield info['gen'](metric, 'alerts._prototyping.NotifiableDiseaseThresholdAlert', reporting_period, loc, district_data)
