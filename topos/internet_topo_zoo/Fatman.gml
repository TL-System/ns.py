graph [
  GeoLocation "Fife and Tayside, UK"
  GeoExtent "Region"
  Network "FatMan"
  Provenance "Primary"
  Note "ATM-based - JANET local provider"
  Source "http://www.fatman.net.uk/"
  Version "1.0"
  Type "REN"
  DateType "Current"
  Backbone 1
  Commercial 0
  label "Fatman"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "01"
  LastAccess "21/01/11"
  Access 0
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 0
  NetworkDate "2011_01"
  DateYear "2011"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Carnegie College"
    Internal 1
    type "Green Node"
  ]
  node [
    id 1
    label "Adam Smith College"
    Internal 1
    type "Green Node"
  ]
  node [
    id 2
    label "Kirkcaldy"
    Country "United Kingdom"
    Longitude -3.16667
    Internal 1
    Latitude 56.11667
    type "Purple Node"
  ]
  node [
    id 3
    label "UoD Fife Campus"
    Internal 1
    type "Blue Node"
  ]
  node [
    id 4
    label "Janet and Internet"
    Internal 0
  ]
  node [
    id 5
    label "None"
    hyperedge 1
    Internal 1
  ]
  node [
    id 6
    label "Janet and Internet"
    Internal 0
  ]
  node [
    id 7
    label "Dundee College"
    Internal 1
    type "Green Node"
  ]
  node [
    id 8
    label "Angus College"
    Internal 1
    type "Green Node"
  ]
  node [
    id 9
    label "Glasgow"
    Country "United Kingdom"
    Longitude -4.25763
    Internal 1
    Latitude 55.86515
    type "Orange Node"
  ]
  node [
    id 10
    label "Leeds"
    Country "United Kingdom"
    Longitude -1.54785
    Internal 1
    Latitude 53.79648
    type "Orange Node"
  ]
  node [
    id 11
    label "RNEP1"
    Country "United Kingdom"
    Longitude -2.96667
    Internal 1
    Latitude 56.5
    type "Purple Node"
  ]
  node [
    id 12
    label "RNEP2"
    Country "United Kingdom"
    Longitude -2.96667
    Internal 1
    Latitude 56.5
    type "Purple Node"
  ]
  node [
    id 13
    label "University of Abertay Dundee"
    Internal 1
    type "Blue Node"
  ]
  node [
    id 14
    label "University of Dundee"
    Internal 1
    type "Blue Node"
  ]
  node [
    id 15
    label "University of St Andrews"
    Internal 1
    type "Blue Node"
  ]
  node [
    id 16
    label "Elmwood College"
    Internal 1
    type "Green Node"
  ]
  edge [
    source 0
    target 2
    LinkLabel "Green Link"
  ]
  edge [
    source 1
    target 2
    LinkLabel "Green Link"
  ]
  edge [
    source 2
    target 3
    LinkLabel "Blue Link"
  ]
  edge [
    source 2
    target 5
    LinkLabel "Purple Link"
  ]
  edge [
    source 4
    target 9
    LinkLabel "Orange Link"
  ]
  edge [
    source 5
    target 11
    id "e12"
  ]
  edge [
    source 5
    target 12
    LinkLabel "Purple Link"
  ]
  edge [
    source 6
    target 10
    LinkLabel "Orange Link"
  ]
  edge [
    source 7
    target 11
    LinkLabel "Green Link"
  ]
  edge [
    source 8
    target 11
    LinkLabel "Green Link"
  ]
  edge [
    source 9
    target 10
    LinkLabel "Orange Link"
  ]
  edge [
    source 9
    target 12
    LinkLabel "Orange/Purple Link"
  ]
  edge [
    source 10
    target 11
    LinkLabel "Orange/Purple Link"
  ]
  edge [
    source 11
    target 12
    LinkLabel "Purple Link"
  ]
  edge [
    source 11
    target 13
    LinkLabel "Blue Link"
  ]
  edge [
    source 11
    target 14
    LinkLabel "Blue Link"
  ]
  edge [
    source 11
    target 15
    LinkLabel "Blue Link"
  ]
  edge [
    source 11
    target 16
    LinkLabel "Green Link"
  ]
  edge [
    source 12
    target 13
    LinkLabel "Blue Link"
  ]
  edge [
    source 12
    target 14
    LinkLabel "Blue Link"
  ]
  edge [
    source 12
    target 15
    LinkLabel "Blue Link"
  ]
]
