import json

p = 'docs/unit-native-program/STATE.json'
d = json.load(open(p, encoding='utf-8'))
d['implementation_head'] = '5a73e31cb6913518bb76a4972599b0dcd8d9413b'
d['current_phase'] = 'P02'
d['phases']['P01'] = {
    'status': 'PASS',
    'report': 'docs/unit-native-program/reports/P01_PHASE_REPORT.md',
    'evidence': [
        'docs/unit-native-program/evidence/mocks/p01/k01-contracts-regeneration.txt',
        'docs/unit-native-program/evidence/mocks/p01/k01-page-regeneration.txt',
        'docs/unit-native-program/evidence/mocks/p01/k01-learn-regeneration.txt',
        'docs/unit-native-program/evidence/mocks/p01/k02-page-views.txt',
        'docs/unit-native-program/evidence/mocks/p01/k02-contracts-vocabulary.txt',
        'docs/unit-native-program/evidence/mocks/p01/k02-learn-content-projection.txt',
        'docs/unit-native-program/evidence/mocks/p01/k03-k04-learn-golden.txt',
        'docs/unit-native-program/evidence/mocks/p01/k04-learn-renderer-goldens.txt',
        'docs/unit-native-program/evidence/mocks/p01/k05-learn-consumer-fixture.txt',
        'docs/unit-native-program/evidence/mocks/p01/k06-contracts-teaching-view.txt',
        'docs/unit-native-program/evidence/mocks/p01/k06-learn-view-separation.txt',
        'packages/lectio-contracts/generated/manifest.json',
        'packages/lectio-page/contracts/manifest.json',
        'packages/lectio-learn/contracts/learn-capability-manifest.json',
    ],
    'blockers': [
        'Full backend pytest suite cannot collect in this environment: pydantic_ai is not installed. Pre-existing and unrelated to P01; the contract-parity tests collect and pass. Install the backend dependency set before P02 gates.'
    ],
}
d['next_action'] = 'Execute P02: shared teaching preparation against the published teaching view at 5a73e31.'
open(p, 'w', encoding='utf-8', newline='\n').write(json.dumps(d, indent=2) + '\n')
print('STATE.json updated')
