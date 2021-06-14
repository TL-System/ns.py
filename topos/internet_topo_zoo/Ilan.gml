graph [
  DateObtained "21/10/10"
  GeoLocation "Israel"
  GeoExtent "Country"
  Network "ILAN"
  Provenance "Primary"
  Access 0
  Source "http://www.iucc.ac.il/eng/info/units/Ilan2.htm"
  Version "1.0"
  Type "REN"
  DateType "Historic"
  Backbone 1
  Commercial 0
  label "Ilan"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 1
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth 0
  LastAccess "21/10/10"
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 1
  Transit 0
  NetworkDate "2008"
  DateYear "2008"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Tel Aviv GigaPoP"
    Country "Israel"
    Longitude 34.76667
    Internal 1
    Latitude 32.06667
    type "Orange Node"
  ]
  node [
    id 1
    label "Int'l backup "
    Internal 0
  ]
  node [
    id 2
    label "IIX"
    Internal 0
  ]
  node [
    id 3
    label "Petach Tikva GigaPoP"
    Country "Israel"
    Longitude 34.88503
    Internal 1
    Latitude 32.09174
    type "Orange Node"
  ]
  node [
    id 4
    label "External Users"
    Internal 0
  ]
  node [
    id 5
    label "GEANT 2 Germany"
    Internal 0
  ]
  node [
    id 6
    label "Open University"
    Country "Israel"
    Longitude 34.86667
    Internal 1
    Latitude 32.18333
    type "Purple Node"
  ]
  node [
    id 7
    label "Haifa University"
    Country "Israel"
    Longitude 34.98917
    Internal 1
    Latitude 32.81556
    type "Purple Node"
  ]
  node [
    id 8
    label "Technion"
    Country "Israel"
    Longitude 34.98917
    Internal 1
    Latitude 32.81556
    type "Purple Node"
  ]
  node [
    id 9
    label "Bar Ilan University"
    Country "Israel"
    Longitude 34.81417
    Internal 1
    Latitude 32.08056
    type "Purple Node"
  ]
  node [
    id 10
    label "Hebrew University"
    Country "Israel"
    Longitude 35.2253
    Internal 1
    Latitude 31.77902
    type "Purple Node"
  ]
  node [
    id 11
    label "Ben Gurion University"
    Country "Israel"
    Longitude 34.95167
    Internal 1
    Latitude 29.56111
    type "Purple Node"
  ]
  node [
    id 12
    label "Weizmann Institute"
    Country "Israel"
    Longitude 34.81861
    Internal 1
    Latitude 31.89694
    type "Purple Node"
  ]
  node [
    id 13
    label "Tel Aviv University"
    Country "Israel"
    Longitude 34.76667
    Internal 1
    Latitude 32.06667
    type "Purple Node"
  ]
  edge [
    source 0
    target 1
    LinkSpeed "600"
    LinkLabel "600Mb/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 600000000.0
  ]
  edge [
    source 0
    target 7
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 0
    target 8
    id "e3"
  ]
  edge [
    source 0
    target 9
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 0
    target 10
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 0
    target 11
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 0
    target 12
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 0
    target 13
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 2
    target 3
    id "e13"
  ]
  edge [
    source 3
    target 4
    id "e11"
  ]
  edge [
    source 3
    target 5
    LinkSpeed "2.5"
    LinkLabel "2.5Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 2500000000.0
  ]
  edge [
    source 3
    target 6
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 3
    target 7
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 3
    target 9
    LinkLabel "300M-1Gb/s"
  ]
  edge [
    source 3
    target 13
    LinkLabel "300M-1Gb/s"
  ]
]
