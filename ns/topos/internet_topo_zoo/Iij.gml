graph [
  DateObtained "21/10/10"
  GeoLocation "Japan, USA"
  GeoExtent "Country+"
  Network "IIJ"
  Provenance "Primary"
  Access 0
  Source "http://www.iij.ad.jp/en/network/backbone/index.html"
  Version "1.0"
  DateType "Historic"
  Type "COM"
  Backbone 1
  Commercial 0
  label "Iij"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 1
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "10"
  LastAccess "3/08/10"
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 1
  Transit 0
  NetworkDate "2010_10"
  DateYear "2010"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Tokyo DC1"
    Country "Japan"
    Longitude 139.5813
    Internal 1
    Latitude 35.61488
  ]
  node [
    id 1
    label "Tokyo DC2"
    Country "Japan"
    Longitude 139.5813
    Internal 1
    Latitude 35.61488
  ]
  node [
    id 2
    label "Sendai DC"
    Country "Japan"
    Longitude 130.3
    Internal 1
    Latitude 31.81667
  ]
  node [
    id 3
    label "Saitama DC"
    Country "Japan"
    Longitude 139.65657
    Internal 1
    Latitude 35.90807
  ]
  node [
    id 4
    label "Nerima DC"
    Country "Japan"
    Longitude 139.65
    Internal 1
    Latitude 35.73333
  ]
  node [
    id 5
    label "Yokohama DC1"
    Country "Japan"
    Longitude 139.6425
    Internal 1
    Latitude 35.44778
  ]
  node [
    id 6
    label "Shibuya DC"
    Country "Japan"
    Longitude 139.7049
    Internal 1
    Latitude 35.65758
  ]
  node [
    id 7
    label "Ikebukuro DC"
    Country "Japan"
    Longitude 139.7115
    Internal 1
    Latitude 35.73023
  ]
  node [
    id 8
    label "Yokohama DC2"
    Country "Japan"
    Longitude 139.6425
    Internal 1
    Latitude 35.44778
  ]
  node [
    id 9
    label "Nagoya DC"
    Country "Japan"
    Longitude 136.90641
    Internal 1
    Latitude 35.18147
  ]
  node [
    id 10
    label "JPNAP Tokyo 1"
    Internal 0
  ]
  node [
    id 11
    label "China"
    Internal 0
  ]
  node [
    id 12
    label "JPNAP Osaka"
    Internal 0
  ]
  node [
    id 13
    label "JPNAP Tokyo 2"
    Internal 0
  ]
  node [
    id 14
    label "NYIIX"
    Internal 0
  ]
  node [
    id 15
    label "PAIX"
    Internal 0
  ]
  node [
    id 16
    label "LAIIX"
    Internal 0
  ]
  node [
    id 17
    label "dix-ie"
    Internal 0
  ]
  node [
    id 18
    label "Equinix exchange"
    Internal 0
  ]
  node [
    id 19
    label "Newyork DC"
    Country "United States"
    Longitude -74.00597
    Internal 1
    Latitude 40.71427
  ]
  node [
    id 20
    label "Fukuoka DC"
    Country "Japan"
    Longitude 130.41806
    Internal 1
    Latitude 33.60639
  ]
  node [
    id 21
    label "Shinsaibashi DC"
    Country "Japan"
    Longitude 135.50031
    Internal 1
    Latitude 34.67511
  ]
  node [
    id 22
    label "Kyoto DC"
    Country "Japan"
    Longitude 135.75385
    Internal 1
    Latitude 35.02107
  ]
  node [
    id 23
    label "Ashburn DC"
    Country "United States"
    Longitude -77.48749
    Internal 1
    Latitude 39.04372
  ]
  node [
    id 24
    label "LA DC"
    Country "United States"
    Longitude -91.15455
    Internal 1
    Latitude 30.45075
  ]
  node [
    id 25
    label "San Jose DC"
    Country "United States"
    Longitude -121.89496
    Internal 1
    Latitude 37.33939
  ]
  node [
    id 26
    label "PaloAlto DC"
    Country "United States"
    Longitude -122.14302
    Internal 1
    Latitude 37.44188
  ]
  node [
    id 27
    label "Okinawa"
    Country "Japan"
    Longitude 127.80139
    Internal 1
    Latitude 26.33583
  ]
  node [
    id 28
    label "Sappora DC"
    Country "Japan"
    Longitude 141.34694
    Internal 1
    Latitude 43.06417
  ]
  node [
    id 29
    label "Chiba"
    Country "Japan"
    Longitude 140.12333
    Internal 1
    Latitude 35.60472
  ]
  node [
    id 30
    label "Tokyo"
    Country "Japan"
    Longitude 139.5813
    Internal 1
    Latitude 35.61488
  ]
  node [
    id 31
    label "Toyama"
    Country "Japan"
    Longitude 137.21139
    Internal 1
    Latitude 36.69528
  ]
  node [
    id 32
    label "Kanazawa"
    Country "Japan"
    Longitude 136.62556
    Internal 1
    Latitude 36.59444
  ]
  node [
    id 33
    label "Hamamatsu"
    Country "Japan"
    Longitude 137.73333
    Internal 1
    Latitude 34.7
  ]
  node [
    id 34
    label "Osaka"
    Country "Japan"
    Longitude 135.50218
    Internal 1
    Latitude 34.69374
  ]
  node [
    id 35
    label "Okayama"
    Country "Japan"
    Longitude 133.935
    Internal 1
    Latitude 34.66167
  ]
  node [
    id 36
    label "Hiroshima"
    Country "Japan"
    Longitude 132.45937
    Internal 1
    Latitude 34.39627
  ]
  edge [
    source 0
    target 6
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 0
    target 30
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 1
    target 6
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 1
    target 30
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 2
    target 6
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 2
    target 30
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 3
    target 6
    LinkType "STM-4"
    LinkLabel "STM-4x2"
    LinkNote "x2"
  ]
  edge [
    source 3
    target 30
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 4
    target 6
    LinkSpeed "10"
    LinkNote "Ex4"
    LinkLabel "10GEx4"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 5
    target 6
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 5
    target 30
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 6
    target 7
    LinkSpeed "10"
    LinkNote "Ex12"
    LinkLabel "10GEx12"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 6
    target 8
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 6
    target 9
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 6
    target 34
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 6
    target 21
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 6
    target 24
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 6
    target 28
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 6
    target 29
    LinkType "STM-4"
    LinkLabel "STM-4"
  ]
  edge [
    source 6
    target 30
    LinkType "STM-4"
    LinkLabel "STM-4"
  ]
  edge [
    source 6
    target 30
    LinkSpeed "10"
    LinkNote "Ex24"
    LinkLabel "10GEx24"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 7
    target 34
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 7
    target 30
    LinkSpeed "10"
    LinkNote "ex12"
    LinkLabel "10Gex12"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 7
    target 13
    LinkSpeed "10"
    LinkLabel "10Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 8
    target 30
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 9
    target 33
    LinkType "STM-1"
    LinkLabel "STM-1"
  ]
  edge [
    source 9
    target 34
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 9
    target 30
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 10
    target 30
    LinkSpeed "30"
    LinkLabel "30Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 30000000000.0
  ]
  edge [
    source 11
    target 34
    LinkType "STM-4"
    LinkLabel "STM-4"
  ]
  edge [
    source 12
    target 34
    LinkSpeed "40"
    LinkLabel "40Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 40000000000.0
  ]
  edge [
    source 14
    target 19
    LinkSpeed "10"
    LinkLabel "10Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 15
    target 19
    LinkSpeed "10"
    LinkLabel "10Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 16
    target 24
    LinkSpeed "1"
    LinkLabel "1Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 1000000000.0
  ]
  edge [
    source 17
    target 30
    LinkSpeed "11"
    LinkLabel "11Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 11000000000.0
  ]
  edge [
    source 18
    target 24
    LinkSpeed "10"
    LinkLabel "10Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 18
    target 25
    LinkSpeed "10"
    LinkLabel "10Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 18
    target 23
    LinkSpeed "10"
    LinkLabel "10Gb/s"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 19
    target 24
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 19
    target 25
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 19
    target 23
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 20
    target 34
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 20
    target 27
    LinkType "STM-4"
    LinkLabel "STM-4x2"
    LinkNote "x2"
  ]
  edge [
    source 20
    target 21
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 21
    target 32
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 21
    target 34
    LinkSpeed "10"
    LinkNote "Ex8"
    LinkLabel "10GEx8"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 21
    target 35
    LinkType "STM-4"
    LinkLabel "STM-4"
  ]
  edge [
    source 21
    target 36
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 21
    target 22
    LinkType "STM-4"
    LinkLabel "STM-4"
  ]
  edge [
    source 21
    target 30
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 22
    target 34
    LinkType "STM-4"
    LinkLabel "STM-4"
  ]
  edge [
    source 23
    target 24
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 23
    target 25
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 24
    target 34
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 24
    target 25
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 24
    target 26
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 25
    target 26
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 25
    target 30
    LinkType "STM-64"
    LinkLabel "STM-64x4"
    LinkNote "x4"
  ]
  edge [
    source 28
    target 30
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
  edge [
    source 29
    target 30
    LinkType "STM-4"
    LinkLabel "STM-4"
  ]
  edge [
    source 30
    target 34
    LinkType "STM-64"
    LinkLabel "STM-64x2"
    LinkNote "x2"
  ]
  edge [
    source 30
    target 33
    LinkType "STM-1"
    LinkLabel "STM-1"
  ]
  edge [
    source 30
    target 31
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 31
    target 32
    LinkType "STM-16"
    LinkLabel "STM-16"
  ]
  edge [
    source 34
    target 35
    LinkType "STM-4"
    LinkLabel "STM-4"
  ]
  edge [
    source 34
    target 36
    LinkType "STM-64"
    LinkLabel "STM-64"
  ]
]
