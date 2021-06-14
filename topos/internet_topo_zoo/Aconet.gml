graph [
  DateObtained "19/10/10"
  GeoLocation "Austria"
  GeoExtent "Country"
  Network "ACOnet"
  Provenance "Primary"
  Note "Vienna is unclear - Internal links show which of two internal PoPs they connect to, but external links not clear."
  Source "http://www.aco.net/ueberblick.html?&amp;L=1"
  Version "1.0"
  Type "REN"
  DateType "Historic"
  Backbone 1
  Commercial 0
  label "Aconet"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "06"
  LastAccess "19/10/10"
  Access 0
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 0
  NetworkDate "2009_06"
  DateYear "2009"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Eisenstadt"
    Country "Austria"
    Longitude 16.51667
    Internal 1
    Latitude 47.85
  ]
  node [
    id 1
    label "St. Polten"
    Country "Austria"
    Longitude 15.63333
    Internal 1
    Latitude 48.2
  ]
  node [
    id 2
    label "Graz2"
    Country "Austria"
    Longitude 15.45
    Internal 1
    Latitude 47.06667
  ]
  node [
    id 3
    label "Leoben"
    Country "Austria"
    Longitude 15.1
    Internal 1
    Latitude 47.38333
  ]
  node [
    id 4
    label "Vienna2"
    Country "Austria"
    Longitude 16.37208
    Internal 1
    Latitude 48.20849
  ]
  node [
    id 5
    label "GEANT"
    Internal 0
  ]
  node [
    id 6
    label "Krems"
    Country "Austria"
    Longitude 15.61415
    Internal 1
    Latitude 48.40921
  ]
  node [
    id 7
    label "Vienna1"
    Country "Austria"
    Longitude 16.37208
    Internal 1
    Latitude 48.20849
  ]
  node [
    id 8
    label "Level3"
    Internal 0
  ]
  node [
    id 9
    label "VIX"
    Internal 0
  ]
  node [
    id 10
    label "None"
    hyperedge 1
    Internal 1
  ]
  node [
    id 11
    label "SANET"
    Internal 0
  ]
  node [
    id 12
    label "CESNET"
    Internal 0
  ]
  node [
    id 13
    label "Klagenfurt2"
    Country "Austria"
    Longitude 14.30528
    Internal 1
    Latitude 46.62472
  ]
  node [
    id 14
    label "Graz1"
    Country "Austria"
    Longitude 15.45
    Internal 1
    Latitude 47.06667
  ]
  node [
    id 15
    label "Linz1"
    Country "Austria"
    Longitude 14.28611
    Internal 1
    Latitude 48.30639
  ]
  node [
    id 16
    label "Linz2"
    Country "Austria"
    Longitude 14.28611
    Internal 1
    Latitude 48.30639
  ]
  node [
    id 17
    label "Salzburg1"
    Country "Austria"
    Longitude 13.04399
    Internal 1
    Latitude 47.79941
  ]
  node [
    id 18
    label "Salzburg2"
    Country "Austria"
    Longitude 13.04399
    Internal 1
    Latitude 47.79941
  ]
  node [
    id 19
    label "Innsbruck1"
    Country "Austria"
    Longitude 11.39454
    Internal 1
    Latitude 47.26266
  ]
  node [
    id 20
    label "Innsbruck2"
    Country "Austria"
    Longitude 11.39454
    Internal 1
    Latitude 47.26266
  ]
  node [
    id 21
    label "Dornbirn"
    Country "Austria"
    Longitude 9.73306
    Internal 1
    Latitude 47.41667
  ]
  node [
    id 22
    label "Klagenfurt1"
    Country "Austria"
    Longitude 14.30528
    Internal 1
    Latitude 46.62472
  ]
  edge [
    source 0
    target 4
    LinkLabel "DWDM"
  ]
  edge [
    source 0
    target 7
    LinkLabel "DWDM"
  ]
  edge [
    source 1
    target 6
    LinkType "Ethernet"
    LinkSpeed "1"
    LinkLabel "1G Ethernet"
    LinkSpeedUnits "G"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 1
    target 7
    LinkType "Ethernet"
    LinkSpeed "1"
    LinkLabel "1G Ethernet"
    LinkSpeedUnits "G"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 2
    target 3
    LinkLabel "DWDM"
  ]
  edge [
    source 2
    target 14
    LinkLabel "DWDM"
  ]
  edge [
    source 2
    target 7
    LinkLabel "DWDM"
  ]
  edge [
    source 3
    target 14
    LinkLabel "DWDM"
  ]
  edge [
    source 4
    target 6
    LinkType "Ethernet"
    LinkSpeed "1"
    LinkLabel "1G Ethernet"
    LinkSpeedUnits "G"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 4
    target 10
    id "e25"
  ]
  edge [
    source 4
    target 13
    LinkLabel "DWDM"
  ]
  edge [
    source 4
    target 14
    LinkLabel "DWDM"
  ]
  edge [
    source 4
    target 15
    LinkLabel "DWDM"
  ]
  edge [
    source 4
    target 18
    LinkLabel "DWDM"
  ]
  edge [
    source 4
    target 19
    LinkLabel "DWDM"
  ]
  edge [
    source 5
    target 10
    LinkType "Ethernet"
    LinkSpeed "10"
    LinkLabel "10G Ethernet"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 7
    target 10
    id "e24"
  ]
  edge [
    source 7
    target 16
    LinkLabel "DWDM"
  ]
  edge [
    source 7
    target 17
    LinkLabel "DWDM"
  ]
  edge [
    source 7
    target 20
    LinkLabel "DWDM"
  ]
  edge [
    source 7
    target 22
    LinkLabel "DWDM"
  ]
  edge [
    source 8
    target 10
    LinkType "Ethernet"
    LinkSpeed "10"
    LinkLabel "10G Ethernet"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 9
    target 10
    LinkType "Ethernet"
    LinkSpeed "10"
    LinkLabel "10G Ethernet"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 10
    target 11
    LinkType "Ethernet"
    LinkSpeed "10"
    LinkLabel "10G Ethernet"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 10
    target 12
    LinkType "Ethernet"
    LinkSpeed "10"
    LinkLabel "10G Ethernet"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 13
    target 22
    LinkLabel "DWDM"
  ]
  edge [
    source 15
    target 16
    LinkLabel "DWDM"
  ]
  edge [
    source 17
    target 18
    LinkLabel "DWDM"
  ]
  edge [
    source 19
    target 20
    LinkLabel "DWDM"
  ]
  edge [
    source 19
    target 21
    LinkLabel "DWDM"
  ]
  edge [
    source 20
    target 21
    LinkLabel "DWDM"
  ]
]
