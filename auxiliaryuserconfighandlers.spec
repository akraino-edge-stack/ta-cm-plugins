# Copyright 2019 Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

Name:       auxiliaryuserconfighandlers
Version:    %{_version}
Release:    1%{?dist}
Summary:    Auxuliary user configuration handlers
License:        %{_platform_licence}
Source0:        %{name}-%{version}.tar.gz
Vendor:         %{_platform_vendor}

BuildArch:      noarch

%define PKG_BASE_DIR /opt/cmframework/userconfighandlers

%description
Auxuliary user configuration handlers


%prep
%autosetup

%build

%install
mkdir -p %{buildroot}/%{PKG_BASE_DIR}/
find auxiliaryuserconfighandlers -name '*.py' -exec cp {} %{buildroot}/%{PKG_BASE_DIR}/ \;

%files
%defattr(0755,root,root,0755)
%{PKG_BASE_DIR}/*.py*

%preun


%postun

%clean
rm -rf ${buildroot}
