graph [
  DateObtained "22/03/11"
  GeoLocation "Europe"
  GeoExtent "Continent"
  Network "NORDU"
  Provenance "Primary"
  Note "CERT + NEWS + DNS"
  Source "https://wiki.nordu.net/display/NORDUwiki/The+History+of+NORDUnet"
  Version "1.0"
  DateType "Historic"
  Type "REN"
  Backbone 1
  Commercial 0
  label "Nordu2005"
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
  NetworkDate "2005"
  DateYear "2005"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "NETNOD"
    Internal 0
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
    label "GEANT"
    Internal 0
  ]
  node [
    id 6
    label "General Internet"
    Internal 0
  ]
  node [
    id 7
    label "St Petersburg"
    Country "Russia"
    Longitude 30.26417
    Internal 1
    Latitude 59.89444
  ]
  node [
    id 8
    label "Oslo"
    Country "Norway"
    Longitude 10.74609
    Internal 1
    Latitude 59.91273
  ]
  edge [
    source 0
    target 1
    LinkLabel "Thin Line"
  ]
  edge [
    source 1
    target 2
    LinkSpeed "5"
    LinkNote " it/s"
    LinkLabel "5 Gbit/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 5000000000.0
  ]
  edge [
    source 1
    target 2
    LinkSpeed "10"
    LinkNote " it/s"
    LinkLabel "10 Gbit/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 1
    target 3
    LinkSpeed "10"
    LinkNote " it/s"
    LinkLabel "10 Gbit/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 1
    target 5
    LinkSpeed "10"
    LinkNote " it/s"
    LinkLabel "10 Gbit/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 1
    target 6
    LinkSpeed "15"
    LinkNote " it/s"
    LinkLabel "15 Gbit/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 15000000000.0
  ]
  edge [
    source 1
    target 7
    LinkSpeed "1"
    LinkNote " it/s"
    LinkLabel "1 Gbit/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 1
    target 8
    LinkSpeed "10"
    LinkNote " it/s"
    LinkLabel "10 Gbit/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 3
    target 8
    LinkSpeed "5"
    LinkNote " it/s"
    LinkLabel "5 Gbit/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 5000000000.0
  ]
  edge [
    source 3
    target 4
    LinkSpeed "155"
    LinkNote " it/s"
    LinkLabel "155 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 155000000.0
  ]
]
