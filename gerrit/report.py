#!/usr/bin/python

import datetime
import json
import sys
import time


CI_SYSTEM = {
    'nova': [
        'Jenkins',
        'Docker CI',
        'Hyper-V CI',
        'IBM PowerKVM Testing',
        'VMware Mine Sweeper',
        'XenServer CI',
        'turbo-hipster',
        ],
    'neutron': [
        'Jenkins',
        'Arista Testing',
        'Big Switch CI',
        'Brocade Tempest',
        'Cisco OpenStack CI Robot',
        'Huawei CI',
        'IBM Neutron Testing',
        'Mellanox External Testing',
        'Midokura CI Bot',
        'NetScaler TestingSystem',
        'Neutron Ryu',
        'Nuage CI',
        'OpenContrail',
        'OpenDaylight Jenkins',
        'PLUMgrid CI',
        'Tail-f NCS Jenkins',
        'VMware Mine Sweeper',
        'nicirabot',
        ]
    }

SENTIMENTS = [
    'Positive',
    'Negative',
    'Positive comment',
    'Negative comment',
    'Negative, buried in comment',
    'Unknown'
    ]


def patch_list_as_html(l):
    out = []
    for p in sorted(l):
        number, patch = p.split(',')
        out.append('<a href="http://review.openstack.org/#/c/%s/%s">%s,%s</a>'
                   % (number, patch, number, patch))
    return ', '.join(out)


def report(project, prefix):
    with open('patchsets.json') as f:
        patchsets = json.loads(f.read())

    # This is more complicated than it looks because we need to handle
    # patchsets which are uploaded so rapidly that older patchsets aren't
    # finished testing.
    total_patches = 0
    total_votes = {}
    missed_votes = {}
    sentiments = {}
    passed_votes = {}
    failed_votes = {}
    unparsed_votes = {}

    for number in patchsets:
        if patchsets[number].get('__exemption__'):
            continue

        if patchsets[number].get('__project__') != project:
            continue
        
        patches = sorted(patchsets[number].keys())
        valid_patches = []

        # Determine how long a patch was valid for. If it wasn't valid for
        # at least three hours, disgard.
        for patch in patches:
            if not '__created__' in patchsets[number][patch]:
                continue

            uploaded = datetime.datetime.fromtimestamp(
                patchsets[number][patch]['__created__'])
            obsoleted = datetime.datetime.fromtimestamp(
                patchsets[number].get(str(int(patch) + 1), {}).get(
                '__created__', time.time()))
            valid_for = obsoleted - uploaded

            if valid_for < datetime.timedelta(hours=3):
                continue

            valid_patches.append(patch)

        total_patches += len(valid_patches)

        for patch in valid_patches:
            for author in patchsets[number][patch]:
                if author == '__created__':
                    continue

                total_votes.setdefault(author, 0)
                total_votes[author] += 1

                for vote, msg, sentiment in patchsets[number][patch][author]:
                    if sentiment.startswith('Positive'):
                        passed_votes.setdefault(author, 0)
                        passed_votes[author] += 1
                    elif sentiment.startswith('Negative'):
                        failed_votes.setdefault(author, 0)
                        failed_votes[author] += 1
                    else:
                        unparsed_votes.setdefault(author, 0)
                        unparsed_votes[author] += 1
                    
                    sentiments.setdefault(author, {})
                    sentiments[author].setdefault(sentiment, [])
                    sentiments[author][sentiment].append(
                        '%s,%s' % (number, patch))

            for author in CI_SYSTEM[prefix]:
                if not author in patchsets[number][patch]:
                    missed_votes.setdefault(author, [])
                    missed_votes[author].append('%s,%s' % (number, patch))

    with open('%s-cireport.html' % prefix, 'w') as f:
        f.write('<b>Valid patches in report period: %d</b><ul>'
                % total_patches)
        for author in CI_SYSTEM[prefix]:
            if not author in total_votes:
                f.write('<li><font color=blue>No votes recorded for '
                        '<b>%s</b></font></li>'
                        % author)
                continue
            
            percentage = (total_votes[author] * 100.0 / total_patches)
            
            if percentage < 95.0:
                f.write('<font color=red>')
                
            passed = passed_votes.get(author, 0)
            failed = failed_votes.get(author, 0)
            unparsed = unparsed_votes.get(author, 0)
            total = passed + failed + unparsed
            pass_percentage = passed * 100.0 / total
            fail_percentage = failed * 100.0 / total
            unparsed_percentage = unparsed * 100.0 / total
            f.write('<li><b>%s</b> voted on %d patchsets (%.02f%%), '
                    'passing %d (%.02f%%), failing %s (%.02f%%) and '
                    'unparsed %d (%.02f%%)'
                    % (author, total_votes[author], percentage, passed,
                       pass_percentage, failed, fail_percentage, unparsed,
                        unparsed_percentage))
                
            if percentage < 95.0:
                  f.write('</font>')

            f.write('</li><ul><li>Missed %d: %s</li>'
                    '<li>Sentiment:</li><ul>'
                    % (len(missed_votes.get(author, [])),
                       patch_list_as_html(
                           missed_votes.get(author, []))))
            for sentiment in SENTIMENTS:
                count = len(sentiments.get(author, {}).get(
                    sentiment, []))
                if count > 0:
                    f.write('<li>%s: %d' % (sentiment, count ))
                    if sentiment != 'Positive':
                        f.write('(%s)</li>'
                                % patch_list_as_html(
                                    sentiments[author][sentiment]))
                f.write('</li>')
            f.write('</ul></ul>')
        f.write('</ul>')


if __name__ == '__main__':
    report ('openstack/nova', 'nova')
    report ('openstack/neutron', 'neutron')
