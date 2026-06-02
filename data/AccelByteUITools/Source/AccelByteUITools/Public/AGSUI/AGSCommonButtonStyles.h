#pragma once

#include "CoreMinimal.h"
#include "CommonButtonBase.h"
#include "AGSCommonButtonStyles.generated.h"

// C++ CommonButtonStyle subclasses that encode the same visual values as the UMG
// inline specs (color, hover, pressed, border, corner radius). Applied automatically
// in UAGSCommonButtonBase::NativePreConstruct based on the Variant property.

UCLASS()
class ACCELBYTEUITOOLS_API UAGSPrimaryButtonStyle : public UCommonButtonStyle
{
	GENERATED_BODY()
public:
	UAGSPrimaryButtonStyle();
};

UCLASS()
class ACCELBYTEUITOOLS_API UAGSSecondaryButtonStyle : public UCommonButtonStyle
{
	GENERATED_BODY()
public:
	UAGSSecondaryButtonStyle();
};

UCLASS()
class ACCELBYTEUITOOLS_API UAGSDangerButtonStyle : public UCommonButtonStyle
{
	GENERATED_BODY()
public:
	UAGSDangerButtonStyle();
};

UCLASS()
class ACCELBYTEUITOOLS_API UAGSIconButtonStyle : public UCommonButtonStyle
{
	GENERATED_BODY()
public:
	UAGSIconButtonStyle();
};
