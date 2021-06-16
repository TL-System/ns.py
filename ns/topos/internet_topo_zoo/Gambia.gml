graph [
  DateObtained "24/01/11"
  GeoLocation "Gambia"
  GeoExtent "Country"
  Network "Gambia"
  Provenance "Secondary"
  Note "Node names hard to read, Country-wide network, not a true provider"
  Source "http://www.nsrc.org/AFRICA/GM/GM-connectivity.gif"
  Version "1.0"
  Type "REN"
  DateType "Historic"
  Backbone 1
  Commercial 0
  label "Gambia"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "07"
  LastAccess "24/01/11"
  Access 0
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 1
  NetworkDate "2001_07"
  DateYear "2001"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Gamnet"
    Internal 1
    type "Commercial ISP"
  ]
  node [
    id 1
    label "Qnet AS"
    Internal 1
    type "Commercial ISP"
  ]
  node [
    id 2
    label "Kerewan"
    Country "Gambia"
    Longitude -16.09111
    Internal 1
    Latitude 13.48944
    type "Core Node"
  ]
  node [
    id 3
    label "Banjul"
    Country "Gambia"
    Longitude -16.57803
    Internal 1
    Latitude 13.45274
    type "Core Node"
  ]
  node [
    id 4
    label "MDI"
    Internal 1
    type "Education/Research"
  ]
  node [
    id 5
    label "GTMI"
    Internal 1
    type "Education/Research"
  ]
  node [
    id 6
    label "Quantum Net"
    Internal 1
    type "Commercial ISP"
  ]
  node [
    id 7
    label "MRC"
    Internal 1
    type "Education/Research"
  ]
  node [
    id 8
    label "Univ Gambia"
    Internal 1
    type "Education/Research"
  ]
  node [
    id 9
    label "GTMI"
    Internal 1
    type "Education/Research"
  ]
  node [
    id 10
    label "Mansk Gambia"
    Internal 1
    type "Other"
  ]
  node [
    id 11
    label "Gamtel House"
    Internal 1
    type "Other"
  ]
  node [
    id 12
    label "Action Ltd"
    Internal 1
    type "NGO/International Organisations"
  ]
  node [
    id 13
    label "UNDP"
    Internal 1
    type "NGO/International Organisations"
  ]
  node [
    id 14
    label "Teleglobe Canada"
    Internal 0
  ]
  node [
    id 15
    label "Intelsat"
    Internal 0
  ]
  node [
    id 16
    label "Earth Station"
    Internal 0
  ]
  node [
    id 17
    label "Gantd Center"
    Internal 1
    type "Other"
  ]
  node [
    id 18
    label "Basse"
    Country "Gambia"
    Longitude -14.21667
    Internal 1
    Latitude 13.31667
    type "Core Node"
  ]
  node [
    id 19
    label "Bansang"
    Country "Gambia"
    Longitude -14.65
    Internal 1
    Latitude 13.43333
    type "Core Node"
  ]
  node [
    id 20
    label "Abuko"
    Country "Gambia"
    Longitude -16.65583
    Internal 1
    Latitude 13.40417
    type "Core Node"
  ]
  node [
    id 21
    label "Serekunda"
    Country "Gambia"
    Longitude -16.67806
    Internal 1
    Latitude 13.43833
    type "Core Node"
  ]
  node [
    id 22
    label "Kotu"
    Country "Gambia"
    Longitude -16.70528
    Internal 1
    Latitude 13.45944
    type "Core Node"
  ]
  node [
    id 23
    label "Bakau"
    Country "Gambia"
    Longitude -16.68194
    Internal 1
    Latitude 13.47806
    type "Core Node"
  ]
  node [
    id 24
    label "Brikama"
    Country "Gambia"
    Longitude -16.64611
    Internal 1
    Latitude 13.2675
    type "Core Node"
  ]
  node [
    id 25
    label "Yundum"
    Country "Gambia"
    Longitude -16.68611
    Internal 1
    Latitude 13.3625
    type "Core Node"
  ]
  node [
    id 26
    label "Soma"
    Country "Gambia"
    Longitude -15.53333
    Internal 1
    Latitude 13.43333
    type "Core Node"
  ]
  node [
    id 27
    label "Farafenni"
    Country "Gambia"
    Longitude -15.6
    Internal 1
    Latitude 13.56667
    type "Core Node"
  ]
  edge [
    source 0
    target 20
    LinkSpeed "10"
    LinkLabel "10 Mbps"
    LinkSpeedUnits "M"
    LinkSpeedRaw 10000000.0
  ]
  edge [
    source 1
    target 20
    LinkSpeed "10"
    LinkLabel "10 Mbps"
    LinkSpeedUnits "M"
    LinkSpeedRaw 10000000.0
  ]
  edge [
    source 2
    target 3
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 2
    target 27
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 3
    target 11
    LinkSpeed "10"
    LinkLabel "10 Mbps"
    LinkSpeedUnits "M"
    LinkSpeedRaw 10000000.0
  ]
  edge [
    source 3
    target 10
    LinkSpeed "64"
    LinkLabel "64 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 3
    target 6
    LinkSpeed "128"
    LinkLabel "128 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 128000.0
  ]
  edge [
    source 3
    target 21
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 4
    target 21
    LinkSpeed "64"
    LinkLabel "64 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 5
    target 21
    LinkSpeed "128"
    LinkLabel "128 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 128000.0
  ]
  edge [
    source 7
    target 23
    LinkSpeed "128"
    LinkLabel "128 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 128000.0
  ]
  edge [
    source 8
    target 21
    LinkSpeed "64"
    LinkLabel "64 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 9
    target 21
    LinkSpeed "64"
    LinkLabel "64 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 12
    target 21
    LinkSpeed "64"
    LinkLabel "64 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 13
    target 23
    LinkSpeed "64"
    LinkLabel "64 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 64000.0
  ]
  edge [
    source 14
    target 15
    LinkType "Satellite"
    LinkLabel "Satellite Link"
    LinkNote " Link"
  ]
  edge [
    source 15
    target 16
    LinkType "Satellite"
    LinkLabel "Satellite Link"
    LinkNote " Link"
  ]
  edge [
    source 16
    target 20
    LinkSpeed "10"
    LinkLabel "10 Mbps"
    LinkSpeedUnits "M"
    LinkSpeedRaw 10000000.0
  ]
  edge [
    source 17
    target 24
    LinkSpeed "10"
    LinkLabel "10 Mbps"
    LinkSpeedUnits "M"
    LinkSpeedRaw 10000000.0
  ]
  edge [
    source 18
    target 26
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 18
    target 19
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 20
    target 21
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 21
    target 22
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 21
    target 23
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 21
    target 24
    LinkSpeed "2"
    LinkNote " it/s (Gamtel Backone)"
    LinkLabel "2 Mbit/s (Gamtel Backbone)"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 21
    target 25
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 25
    target 26
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
  edge [
    source 26
    target 27
    LinkSpeed "2"
    LinkNote " it/s"
    LinkLabel "2 Mbit/s"
    LinkSpeedUnits "M"
    LinkSpeedRaw 2000000.0
  ]
]
