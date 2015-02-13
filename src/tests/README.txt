The scripts to run the tests can be found in the directory above this one.
The Ansible integration tests require password logins via ssh to be possible,
and also another user, lxle1, must be configured to test running things as a
user other than the current user. Both the current user and lxle1 must have
passwordless logins enabled via ssh, and further the tests that use the lxle1
user require a private key named 'lxle1-dev-key' to be able to facilitate the
passwordless login to the local host.

If you DON'T want to test Ansible integration, you can just run the
do_quick_tests.bsh script, and the Ansible tests will be skipped. Alternatively,
you can modify the user/keyfile used in the tests so you don't need to add a
lxle1 user.
 