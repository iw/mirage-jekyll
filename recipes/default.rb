
# Support for adding PPAs
# https://help.ubuntu.com/community/Repositories/Ubuntu#Adding_PPAs
package 'python-software-properties'

apt_repository 'avsm-ppa-precise' do
  uri 'http://ppa.launchpad.net/avsm/ppa/ubuntu'
  distribution 'precise'
  components ['main']
  deb_src true
end

package 'ocaml' do
  version '4.01.0-1ppa4~precise'
  options '--force-yes'
end

%w{opam ocaml-native-compilers camlp4-extra m4}.each do |pkg|
  package pkg do
    options '--force-yes'
  end
end
