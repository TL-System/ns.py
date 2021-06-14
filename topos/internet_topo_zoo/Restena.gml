graph [
  DateObtained "3/02/11"
  GeoLocation "Luxembourg"
  GeoExtent "Country"
  Network "Restena"
  Provenance "Primary"
  Access 0
  Source "http://www.restena.lu/restena/fr/FR-NationalNetwork.html"
  Version "1.0"
  Type "REN"
  DateType "Current"
  Backbone 1
  Commercial 0
  label "Restena"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 1
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "03"
  LastAccess "6/03/11"
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 0
  NetworkDate "2011_03"
  DateYear "2011"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Walferdange"
    Country "Luxembourg"
    Longitude 6.13722
    Internal 1
    Latitude 49.65833
  ]
  node [
    id 1
    label "CCRN"
    Country "Luxembourg"
    Longitude 6.13
    Internal 1
    Latitude 49.61167
  ]
  node [
    id 2
    label "Ettelbruck"
    Country "Luxembourg"
    Longitude 6.10417
    Internal 1
    Latitude 49.8475
  ]
  node [
    id 3
    label "Diekirch"
    Country "Luxembourg"
    Longitude 6.15583
    Internal 1
    Latitude 49.86778
  ]
  node [
    id 4
    label "GEANT Paris (FR)"
    Internal 0
  ]
  node [
    id 5
    label "Internet via Bruxelles (BE)"
    Internal 0
  ]
  node [
    id 6
    label "ADSL (via EPT)"
    Internal 1
  ]
  node [
    id 7
    label "France"
    Internal 0
  ]
  node [
    id 8
    label "GEANT Frankfurt (DE)"
    Internal 0
  ]
  node [
    id 9
    label "RESTENA"
    Country "Luxembourg"
    Longitude 6.14944
    Internal 1
    Latitude 49.62389
  ]
  node [
    id 10
    label "BCE"
    Country "Luxembourg"
    Longitude 6.14944
    Internal 1
    Latitude 49.62389
  ]
  node [
    id 11
    label "ADSL (via Tango)"
    Internal 1
  ]
  node [
    id 12
    label "UNI.iu"
    Country "Luxembourg"
    Longitude 6.12167
    Internal 1
    Latitude 49.62083
  ]
  node [
    id 13
    label "Rollingergrund"
    Country "Luxembourg"
    Longitude 6.10778
    Internal 1
    Latitude 49.62278
  ]
  node [
    id 14
    label "Campus Geesseknaeppchen"
    Country "Luxembourg"
    Longitude 6.12417
    Internal 1
    Latitude 49.6025
  ]
  node [
    id 15
    label "Esch-sur-Alzette"
    Country "Luxembourg"
    Longitude 5.98056
    Internal 1
    Latitude 49.49583
  ]
  node [
    id 16
    label "Bettembourg"
    Country "Luxembourg"
    Longitude 6.10278
    Internal 1
    Latitude 49.51861
  ]
  node [
    id 17
    label "Luxembourg"
    Country "Luxembourg"
    Longitude 6.13
    Internal 1
    Latitude 49.61167
  ]
  node [
    id 18
    label "Limpertsberg"
    Country "Luxembourg"
    Longitude 6.12167
    Internal 1
    Latitude 49.62083
  ]
  edge [
    source 0
    target 9
    LinkType "Fiber"
    LinkLabel "Managed Fiber (10Gbps, 100Mbps)"
    LinkNote "Managed  (10Gbps, 100Mbps)"
  ]
  edge [
    source 1
    target 9
    LinkType "Fiber"
    LinkLabel "Managed Fiber (10Gbps, 100Mbps)"
    LinkNote "Managed  (10Gbps, 100Mbps)"
  ]
  edge [
    source 2
    target 10
    LinkType "Fiber"
    LinkSpeed "1"
    LinkSpeedUnits "G"
    LinkNote "Dark  ()"
    LinkLabel "Dark Fiber (1Gbps)"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 2
    target 3
    LinkType "Fiber"
    LinkSpeed "1"
    LinkSpeedUnits "G"
    LinkNote "Dark  ()"
    LinkLabel "Dark Fiber (1Gbps)"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 3
    target 9
    LinkType "Fiber"
    LinkLabel "Managed Fiber (10Gbps, 100Mbps)"
    LinkNote "Managed  (10Gbps, 100Mbps)"
  ]
  edge [
    source 4
    target 10
    LinkLabel "International Connectivity (1-10 Gbps)"
  ]
  edge [
    source 5
    target 10
    LinkLabel "International Connectivity (1-10 Gbps)"
  ]
  edge [
    source 6
    target 9
    LinkType "Fiber"
    LinkLabel "Managed Fiber (10Gbps, 100Mbps)"
    LinkNote "Managed  (10Gbps, 100Mbps)"
  ]
  edge [
    source 7
    target 15
    LinkLabel "International Connectivity (1-10 Gbps)"
  ]
  edge [
    source 8
    target 10
    LinkLabel "International Connectivity (1-10 Gbps)"
  ]
  edge [
    source 9
    target 10
    LinkType "Fiber"
    LinkLabel "Dark Fiber (1-10Gbps)"
    LinkNote "Dark  (1-10Gbps)"
  ]
  edge [
    source 9
    target 16
    LinkType "Fiber"
    LinkLabel "Dark Fiber (1-10Gbps)"
    LinkNote "Dark  (1-10Gbps)"
  ]
  edge [
    source 9
    target 17
    LinkType "Fiber"
    LinkLabel "Dark Fiber (1-10Gbps)"
    LinkNote "Dark  (1-10Gbps)"
  ]
  edge [
    source 10
    target 11
    LinkType "Fiber"
    LinkLabel "Managed Fiber (10Gbps, 100Mbps)"
    LinkNote "Managed  (10Gbps, 100Mbps)"
  ]
  edge [
    source 10
    target 18
    LinkType "Fiber"
    LinkSpeed "1"
    LinkSpeedUnits "G"
    LinkNote "Dark  ()"
    LinkLabel "Dark Fiber (1Gbps)"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 12
    target 18
    LinkType "Fiber"
    LinkSpeed "1"
    LinkSpeedUnits "G"
    LinkNote "Dark  ()"
    LinkLabel "Dark Fiber (1Gbps)"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 12
    target 14
    LinkType "Fiber"
    LinkSpeed "1"
    LinkSpeedUnits "G"
    LinkNote "Dark  ()"
    LinkLabel "Dark Fiber (1Gbps)"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 13
    target 14
    LinkType "Fiber"
    LinkSpeed "1"
    LinkSpeedUnits "G"
    LinkNote "Dark  ()"
    LinkLabel "Dark Fiber (1Gbps)"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 14
    target 17
    LinkType "Fiber"
    LinkLabel "Dark Fiber (1-10Gbps)"
    LinkNote "Dark  (1-10Gbps)"
  ]
  edge [
    source 14
    target 15
    LinkType "Fiber"
    LinkLabel "Dark Fiber (1-10Gbps)"
    LinkNote "Dark  (1-10Gbps)"
  ]
  edge [
    source 15
    target 16
    LinkType "Fiber"
    LinkLabel "Dark Fiber (1-10Gbps)"
    LinkNote "Dark  (1-10Gbps)"
  ]
]
