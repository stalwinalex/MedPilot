#import <Foundation/Foundation.h>
#import <Vision/Vision.h>

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 2) {
            fprintf(stderr, "Usage: apple_vision_ocr <image_path>\n");
            return 1;
        }

        NSString *filePath = [NSString stringWithUTF8String:argv[1]];
        NSURL *fileURL = [NSURL fileURLWithPath:filePath];

        VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];
        request.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
        request.usesLanguageCorrection = YES;

        VNImageRequestHandler *handler = [[VNImageRequestHandler alloc] initWithURL:fileURL options:@{}];
        NSError *error = nil;
        [handler performRequests:@[request] error:&error];

        if (error) {
            fprintf(stderr, "Vision Error: %s\n", [[error localizedDescription] UTF8String]);
            return 1;
        }

        // Sort observations top to bottom (in Vision coordinates, y=1.0 is top)
        NSArray *sorted = [request.results sortedArrayUsingComparator:^NSComparisonResult(VNRecognizedTextObservation *a, VNRecognizedTextObservation *b) {
            // Compare Y descending (top to bottom)
            if (a.boundingBox.origin.y > b.boundingBox.origin.y + 0.02) {
                return NSOrderedAscending;
            } else if (b.boundingBox.origin.y > a.boundingBox.origin.y + 0.02) {
                return NSOrderedDescending;
            }
            // Same line (approximate y), sort X ascending (left to right)
            if (a.boundingBox.origin.x < b.boundingBox.origin.x) {
                return NSOrderedAscending;
            } else {
                return NSOrderedDescending;
            }
        }];

        for (VNRecognizedTextObservation *obs in sorted) {
            VNRecognizedText *top = [[obs topCandidates:1] firstObject];
            if (top && top.string.length > 0) {
                printf("%s\n", [top.string UTF8String]);
            }
        }
    }
    return 0;
}
