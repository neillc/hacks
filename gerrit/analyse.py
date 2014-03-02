#!/usr/bin/python

import datetime
import json
import sys
import urllib


# This list from https://review.openstack.org/#/admin/groups/270,members and
# https://review.openstack.org/#/admin/groups/91,members
CI_SYSTEM = ['Jenkins',
             'Arista Testing',
             'Big Switch CI',
             'Brocade Tempest',
             'Cisco OpenStack CI Robot',
             'CitrixJenkins',
             'Compass CI',
             'Designate Jenkins',
             'Docker CI',
             'Freescale CI',
             'Fuel CI',
             'Huawei CI',
             'Hyper-V CI',
             'IBM DB2 Test',
             'IBM Neutron Testing',
             'IBM PowerKVM Testing',
             'IBM PowerVC Test',
             'Mellanox External Testing',
             'Metaplugin CI Test',
             'Midokura CI Bot',
             'NEC OpenStack CI',
             'NetScaler TestingSystem',
             'Neutron Ryu',
             'Nuage CI',
             'OpenContrail',
             'OpenDaylight Jenkins',
             'PLUMgrid CI',
             'Puppet Ceph Integration',
             'Puppet OpenStack CI',
             'Radware 3rd Party Testing',
             'Red Hat CI',
             'SmokeStack',
             'Tail-f NCS Jenkins',
             'VMware Mine Sweeper',
             'Wherenow.org Jenkins CI',
             'XenServer CI',
             'murano-ci',
             'nicirabot',
             'novaimagebuilder-jenkins',
             'reddwarf',
             'savanna-ci',
             'turbo-hipster',
             'vArmour CI Test',
             'vanillabot',
        ]


def read_remote_lines(url):
    remote = urllib.urlopen(url)
    data = ''
    while True:
        d = remote.read(100)
        if not d:
            break

        data += d

        if data.find('\n') != -1:
            elems = data.split('\n')
            for line in elems[:-1]:
                yield line
            data = elems[-1]

    if data:
        yield data


if __name__ == '__main__':
    patchsets = {}
    skipped_authors = {}
    day = datetime.datetime.now()
    day -= datetime.timedelta(days=7)

    while day < datetime.datetime.now():
        print 'Processing %s/%s/%s' % (day.year, day.month, day.day)
        for line in read_remote_lines('http://www.rcbops.com/gerrit/merged/'
                                      '%s/%s/%s'
                                      % (day.year, day.month, day.day)):
            try:
                j = json.loads(line)
            except:
                continue

            try:
                if not 'change' in j:
                    continue
                if j['change']['branch'] != 'master':
                    continue

                if j['type'] == 'patchset-created':
                    number = j['change']['number']
                    patchset = j['patchSet']['number']
                    timestamp = j['patchSet']['createdOn']
                    patchsets.setdefault(number, {})
                    patchsets[number][patchset] = {
                        '__created__': timestamp
                        }
                    patchsets[number]['__project__'] = j['change']['project']

                elif j['type'] == 'comment-added':
                    if j['comment'].startswith('Starting check jobs'):
                        continue
                    if j['comment'].startswith('Starting gate jobs'):
                        continue

                    if not 'approvals' in j:
                        j['approvals'] = [{'type': 'CRVW', 'value': 0}]

                    author = j['author']['name']
                    if not author in CI_SYSTEM:
                        skipped_authors.setdefault(author, 0)
                        skipped_authors[author] += 1
                        continue

                    number = j['change']['number']
                    patchset = j['patchSet']['number']
                    patchsets.setdefault(number, {})
                    patchsets[number].setdefault(patchset, {})

                    verified = []
                    if author in patchsets[number].get(patchset, {}):
                        verified = patchsets[number][patchset][author]
                    for approval in j['approvals']:
                        # People who are sane
                        if approval.get('value') in ['1', '2']:
                            sentiment = 'Positive'
                        elif approval.get('value') in ['-1', '-2']:
                            sentiment = 'Negative'

                        # Horrible special cases
                        elif (author == 'Hyper-V CI'
                              and j['comment'].startswith('Build succeeded.')
                              and j['comment'].find(
                                  'Test run failed in') != -1):
                            sentiment = 'Negative, buried in comment'
                        elif (author == 'XenServer CI'
                              and j['comment'].startswith('Passed using')):
                            sentiment = 'Positive comment'
                        elif (author == 'XenServer CI'
                              and j['comment'].startswith('Failed using')):
                            sentiment = 'Negative comment'
                        elif (author == 'Arista Testing'
                              and j['comment'].find('Arista third party '
                                                    'testing FAILED') != -1):
                            sentiment = 'Negative, buried in a comment'
                        elif (author == 'Big Switch CI'
                              and j['comment'].startswith('Doesn\'t seem to '
                                                          'work')):
                            sentiment = 'Negative, buried in a comment'

                        # Normal people special cases
                        elif j['comment'].startswith('Build succeeded.'):
                            sentiment = 'Positive comment'
                        elif j['comment'].startswith('Build successful.'):
                            sentiment = 'Positive comment'
                        elif j['comment'].startswith('Build failed.'):
                            sentiment = 'Negative comment'
                        else:
                            sentiment = 'Unknown'
                        
                        verified.append(('%s:%s' % (approval['type'],
                                                    approval.get('value')),
                                         j['comment'].split('\n')[0],
                                         sentiment))
                    patchsets[number][patchset][author] = verified

                elif j['type'] in ['change-abandoned',
                                   'change-merged']:
                    # These special cases might cause a CI system to stop
                    # running its tests
                    number = j['change']['number']
                    patchsets.setdefault(number, {})
                    patchsets[number]['__exemption__'] = j['type']

                elif j['type'] in ['change-restored',
                                   'ref-updated']:
                    pass

                else:
                    print json.dumps(j, indent=4)
                    sys.exit(0)

            except Exception, e:
                print 'Error: %s\n' % e
                print json.dumps(j, indent=4)
                sys.exit(0)

        day += datetime.timedelta(days=1)

    # Write some json blobs, which are intended mostly for debugging
    with open('patchsets.json', 'w') as f:
        f.write(json.dumps(patchsets, indent=4))
    with open('skipped.json', 'w') as f:
        f.write(json.dumps(skipped_authors, indent=4))
