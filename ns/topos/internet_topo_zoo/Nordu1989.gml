graph [
  DateObtained "22/03/11"
  GeoLocation "Europe"
  GeoExtent "Continent"
  Network "NORDU"
  Provenance "Primary"
  Note "CERT + NEWS + DNS Speeds from 'The History of Nordunet', pg 45"
  Source "https://wiki.nordu.net/display/NORDUwiki/The+History+of+NORDUnet"
  Version "1.0"
  Type "REN"
  DateType "Historic"
  Backbone 1
  Commercial 0
  label "Nordu1989"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth 0
  LastAccess "22/03/11"
  Access 0
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 1
  Transit 0
  NetworkDate "1989"
  DateYear "1989"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Trondheim"
    Country "Norway"
    Longitude 10.39506
    Internal 1
    Latitude 63.43049
  ]
  node [
    id 1
    label "Stockholm"
    Country "Sweden"
    Longitude 18.0649
    Internal 1
    Latitude 59.33258
  ]
  node [
    id 2
    label "Helsinki"
    Country "Finland"
    Longitude 24.93545
    Internal 1
    Latitude 60.16952
  ]
  node [
    id 3
    label "Copenhagen"
    Country "Denmark"
    Longitude 12.56553
    Internal 1
    Latitude 55.67594
  ]
  node [
    id 4
    label "Reykjavik"
    Country "Iceland"
    Longitude -21.89541
    Internal 1
    Latitude 64.13548
  ]
  node [
    id 5
    label "EUROPE"
    Internal 0
  ]
  node [
    id 6
    label "USA"
    Internal 0
  ]
  edge [
    source 0
    target 1
    LinkSpeed "64"
    LinkNote " it/s"
    LinkLabel "64 Kbit/s"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 1
    target 2
    LinkSpeed "64"
    LinkNote " it/s"
    LinkLabel "64 Kbit/s"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 1
    target 3
    LinkSpeed "64"
    LinkNote " it/s"
    LinkLabel "64 Kbit/s"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 1
    target 5
    LinkSpeed "64"
    LinkNote " it/s"
    LinkLabel "64 Kbit/s"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 1
    target 6
    LinkSpeed "64"
    LinkNote " it/s"
    LinkLabel "64 Kbit/s"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 3
    target 4
    LinkLabel "9600 bit/s"
  ]
]
