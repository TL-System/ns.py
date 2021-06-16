graph [
  DateObtained "2/01/11"
  GeoLocation "Serbia, Montenegro"
  GeoExtent "Country+"
  Network "TelecomSerbia"
  Provenance "Unknown"
  Access 0
  Source "http://chaisuk.wordpress.com/2008/09/21/internet-technology-nonviolent-struggle-serbia3/"
  Version "1.0"
  Type "COM"
  DateType "Historic"
  Backbone 0
  Commercial 0
  label "Telecomserbia"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth 0
  LastAccess "2/01/11"
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 0
  NetworkDate "2005"
  DateYear "2005"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Novi Sad"
    Country "Serbia"
    Longitude 19.83694
    Internal 1
    Latitude 45.25167
    type "GSR12410"
  ]
  node [
    id 1
    label "Belgrade"
    Country "Serbia"
    Longitude 20.46513
    Internal 1
    Latitude 44.80401
    type "GSR12410"
  ]
  node [
    id 2
    label "Kragujevac"
    Country "Serbia"
    Longitude 20.91667
    Internal 1
    Latitude 44.01667
    type "GSR12410"
  ]
  node [
    id 3
    label "Nis"
    Country "Serbia"
    Longitude 21.90333
    Internal 1
    Latitude 43.32472
    type "GSR12410"
  ]
  node [
    id 4
    label "Krusevac"
    Country "Serbia"
    Longitude 21.33389
    Internal 1
    Latitude 43.58
    type "GSR12410"
  ]
  node [
    id 5
    label "Podgorica"
    Country "Montenegro"
    Longitude 19.26361
    Internal 1
    Latitude 42.44111
    type "GSR12410"
  ]
  edge [
    source 0
    target 1
    LinkLabel "DTP-Ring 2.5 Gbit/s"
  ]
  edge [
    source 0
    target 5
    LinkLabel "DTP-Ring 2.5 Gbit/s"
  ]
  edge [
    source 1
    target 2
    LinkLabel "DTP-Ring 2.5 Gbit/s"
  ]
  edge [
    source 2
    target 3
    LinkLabel "DTP-Ring 2.5 Gbit/s"
  ]
  edge [
    source 3
    target 4
    LinkLabel "DTP-Ring 2.5 Gbit/s"
  ]
  edge [
    source 4
    target 5
    LinkLabel "DTP-Ring 2.5 Gbit/s"
  ]
]
